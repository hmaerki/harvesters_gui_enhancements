import sys
import enum

from PyQt5.QtCore import QTimer


from harvesters.core import Harvester

from util_harvesters.image_buffer import (
    ImageReaderThread,
    SAVE_IMAGE_TO_FILE,
    PRINT_PROGRESS,
    ImageBuffer,
)
from main_window import QtWidgets, Ui_MainWindow
import camera_config


# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
# logger = logging.getLogger(name='harvesters')
# logger.setLevel(logging.DEBUG)
# logger = logging.getLogger(name='harvesters.core')
# logger.setLevel(logging.DEBUG)
# logger = get_logger(name=__name__)


class EnumRunning(enum.Enum):
    STARTED = enum.auto()
    STOPPED = enum.auto()
    INTRANSITION = enum.auto()

    @property
    def button_start_enabled(self):
        return self == EnumRunning.STOPPED

    @property
    def button_stop_enabled(self):
        return self == EnumRunning.STARTED


class StateRunning:
    def __init__(self, ui: Ui_MainWindow):
        self._state: EnumRunning = EnumRunning.STOPPED
        self._ui = ui
        self.update(new_state=EnumRunning.STOPPED)

    def update(self, new_state: EnumRunning):
        self._state = new_state
        self._ui.startButton.setEnabled(self._state.button_start_enabled)
        self._ui.stopButton.setEnabled(self._state.button_stop_enabled)


class HarvesterMain:
    def __init__(self):
        self._app = QtWidgets.QApplication(sys.argv)
        self._main_windows = QtWidgets.QMainWindow()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self._main_windows)
        self._state_running = StateRunning(self._ui)
        self._image_reader_thread: ImageReaderThread = None
        self._harvester_core: Harvester = None

        self._init_harvester()
        self._init_status_buttons()

    def _init_harvester(self):
        self._harvester_core = Harvester()
        self._harvester_core.reset()
        for camera in camera_config.CAMERAS:
            if camera.FILENAME_CTI.exists():
                print(f"Add {camera.FILENAME_CTI}")
                self._harvester_core.add_file(
                    file_path=str(camera.FILENAME_CTI),
                    check_existence=True,
                    check_validity=True,
                )
        self._harvester_core.update()

        timer = QTimer(self._app)
        timer.timeout.connect(self._worker_update_statistics)
        timer.start(1000)

    def _worker_update_statistics(self):
        if self._image_reader_thread is None:
            return
        statistics = self._image_reader_thread.statistics

        self._ui.statusbar.showMessage(statistics)

    def _init_status_buttons(self):
        def image_acquired(image_buffer: ImageBuffer) -> None:
            image = image_buffer.image
            assert image is not None

            if PRINT_PROGRESS:
                print(f"Progress {image_buffer.i}: {image} slot", flush=True)
            if SAVE_IMAGE_TO_FILE:
                image.save(f"image_{image_buffer.i:06d}_slot.bmp")

            self._ui.imageviewer.setImage(image)
            image_buffer.release()

        def done() -> None:
            self._state_running.update(EnumRunning.STOPPED)

        def start():
            camera = camera_config.CameraBasler()
            camera = camera_config.CameraSimulation()
            ia = self._harvester_core.create_image_acquirer(**camera.ACQUIRER_QUERY)

            camera.configure(ia)

            self._image_reader_thread = ImageReaderThread(
                parent=self._app, ia=ia, frame_pre_s=camera.FRAME_PER_S
            )
            if True:
                self._image_reader_thread.image_acquired.connect(image_acquired)
                self._image_reader_thread.done.connect(done)
                self._image_reader_thread.start()
            else:
                self._image_reader_thread.run()

            self._state_running.update(EnumRunning.STARTED)

        def stop():
            if self._image_reader_thread is None:
                return
            self._state_running.update(EnumRunning.INTRANSITION)

            self._image_reader_thread.stop_acquisition()
            self._image_reader_thread = None
            self._harvester_core.reset()

        self._ui.startButton.pressed.connect(start)
        self._ui.stopButton.pressed.connect(stop)

    def run(self):
        self._main_windows.show()
        sys.exit(self._app.exec_())


def main():
    harvester_main = HarvesterMain()
    harvester_main.run()


if __name__ == "__main__":
    main()
