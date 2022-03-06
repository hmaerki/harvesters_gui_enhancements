import itertools
import datetime

import numpy as np

from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtGui import QImage

from genicam.gentl import PAYLOADTYPE_INFO_IDS
from harvesters.util.pfnc import (
    is_custom,
    get_bits_per_pixel,
    bgr_formats,
    mono_location_formats,
    rgb_formats,
    rgba_formats,
    bgra_formats,
    bayer_location_formats,
)

from harvesters.core import ImageAcquirer, TimeoutException, Buffer
PATCHED_HARVESTERS = None
if PATCHED_HARVESTERS:
    from harvesters.core import _is_logging_buffer_manipulation, _logger, _family_tree

SAVE_IMAGE_TO_FILE = False
PRINT_PROGRESS = False

_VISIBLE_PAYLOADS = [
    PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_IMAGE,
    PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_CHUNK_DATA,
    PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_MULTI_PART,
]


class _BufferPool:
    "Singleton required for cleaning up properly"

    def __init__(self):
        self._buffers_in_use = 0

    def increment(self):
        self._buffers_in_use += 1

    def decrement(self):
        assert self._buffers_in_use > 0
        self._buffers_in_use -= 1

    @property
    def buffers_in_use(self) -> bool:
        assert self._buffers_in_use >= 0
        return self._buffers_in_use > 0

    def reset(self) -> None:
        self._buffers_in_use = 0


_BUFFER_BOOL = _BufferPool()


class ImageBuffer:
    def __init__(self, i: int, buffer: Buffer):
        assert isinstance(i, int)
        assert isinstance(buffer, Buffer)
        assert buffer is not None
        _BUFFER_BOOL.increment()
        self._i = i
        self._buffer = buffer

    def release(self) -> None:
        _BUFFER_BOOL.decrement()
        self._buffer.queue()
        self._buffer = None

    @property
    def i(self) -> int:
        return self._i

    @property
    def image(self) -> QImage:
        #
        payload = self._buffer.payload
        component = payload.components[0]
        width = component.width
        height = component.height

        #
        exponent = 0
        data_format = None

        #
        data_format_value = component.data_format_value
        if is_custom(data_format_value):
            return

        data_format = component.data_format
        bpp = get_bits_per_pixel(data_format)
        if bpp is None:
            return
        exponent = bpp - 8

        # Reshape the image so that it can be drawn on the
        # VisPy canvas:
        if (
            data_format in mono_location_formats
            or data_format in bayer_location_formats
        ):
            # Reshape the 1D NumPy array into a 2D so that VisPy
            # can display it as a mono image:
            content = component.data.reshape(height, width)
        else:
            # The image requires you to reshape it to draw it on the
            # canvas:
            if (
                data_format in rgb_formats
                or data_format in rgba_formats
                or data_format in bgr_formats
                or data_format in bgra_formats
            ):
                # Reshape the 1D NumPy array into a 2D so that VisPy
                # can display it as an RGB image:
                content = component.data.reshape(
                    height,
                    width,
                    int(component.num_components_per_pixel),
                )
                #
                if data_format in bgr_formats:
                    # Swap every R and B so that VisPy can display
                    # it as an RGB image:
                    content = content[:, :, ::-1]
            else:
                return

        # Convert each data to an 8bit.
        if exponent > 0:
            # The following code may affect to the rendering
            # performance:
            content = content / (2**exponent)

            # Then cast each array element to an uint8:
            content = content.astype(np.uint8)

        height2, width2, _ = content.shape
        return QImage(content.data, width2, height2, 3 * width2, QImage.Format_RGB888)


class ImageReaderThread(QThread):
    done = pyqtSignal()
    image_acquired = pyqtSignal(ImageBuffer)

    def __init__(self, parent: QObject, ia: ImageAcquirer, frame_pre_s: float):
        assert isinstance(parent, QObject)
        assert isinstance(ia, ImageAcquirer)
        assert isinstance(frame_pre_s, float)
        self._stop_acquisition = False
        self._ia = ia
        self._frame_per_s = frame_pre_s
        _BUFFER_BOOL.reset()
        super().__init__(parent=parent)

    def stop_acquisition(self):
        self._stop_acquisition = True

    def run(self):
        """Long-running task."""
        # https://github.com/genicam/harvesters
        self._ia.start_acquisition(run_in_background=False)

        event_manager = self._ia._event_new_buffer_managers[
            0
        ]  # pylint: disable=protected-access
        # RATIONALE
        # 'event_manager.update_event_data()' seems to consume a lot of cpu.
        # So we try to remain as short as possible.
        # The rest of the time we remain in 'self.msleep()'
        timeout_after_image_acquistion_ms = int(1000.0 * 0.9 / self._frame_per_s)
        timeout_for_image_acquisition_ms = int(1000.0 * 0.2 / self._frame_per_s)
        for i in itertools.count():
            if not self._ia.is_acquiring():
                break
            if self._stop_acquisition:
                # waiting till all buffers has been displayed
                if _BUFFER_BOOL.buffers_in_use:
                    self._ia.stop_acquisition()
                break

            def handle_one_buffer(i: int):
                try:
                    self.msleep(timeout_after_image_acquistion_ms)
                    event_manager.update_event_data(timeout_for_image_acquisition_ms)
                except TimeoutException:
                    if PATCHED_HARVESTERS:
                        _logger.info("TimeoutException")
                    return
                genicam_buffer = event_manager.buffer

                def queue_buffer(msg: str):
                    if PATCHED_HARVESTERS:
                        _logger.info(f"Discard buffer: {msg}")
                    genicam_buffer.parent.queue_buffer(genicam_buffer)

                if not genicam_buffer.is_complete():
                    queue_buffer("The acquired buffer was incomplete")
                    return
                if genicam_buffer.payload_type not in _VISIBLE_PAYLOADS:
                    queue_buffer("Buffer not visible")
                    return
                if self._stop_acquisition:
                    queue_buffer("Stopping acquisition")
                    return

                if PATCHED_HARVESTERS:
                    if _is_logging_buffer_manipulation:
                        _logger.debug(
                            f"{self} has fetched buffer {genicam_buffer.context}"
                            f" containing frame {genicam_buffer.frame_id}"
                            f" from {_family_tree(event_manager.parent)}"
                        )

                buffer = Buffer(
                    buffer=genicam_buffer, node_map=self._ia.remote_device.node_map
                )
                if PRINT_PROGRESS:
                    print(f"Progress {i}: A", flush=True)

                self._update_statistics(buffer=buffer)
                self.image_acquired.emit(ImageBuffer(i=i, buffer=buffer))
                if PRINT_PROGRESS:
                    print(f"Progress {i}: B", flush=True)

            handle_one_buffer(i)

        self._ia.destroy()
        self._ia = None

        self.done.emit()

    def _update_statistics(self, buffer) -> None:
        assert buffer
        self._ia.statistics.increment_num_images()
        self._ia.statistics.update_timestamp(buffer)

    @property
    def statistics(self) -> str:
        if self._ia is None:
            return "stopped"
        node_map = self._ia.remote_device.node_map
        elapsed = datetime.timedelta(seconds=int(self._ia.statistics.elapsed_time_s))
        list_labels = [
            f"{node_map.Width.value}x{node_map.Height.value}",
            node_map.PixelFormat.value,
            f"{self._ia.statistics.fps:.1f} fps",
            f"elapsed {elapsed}",
            f"{self._ia.statistics.num_images} images",
        ]
        return " ".join(list_labels)
