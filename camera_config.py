import pathlib
from typing import overload

import genicam
from genicam import genapi

from harvesters.core import ImageAcquirer


DIRECTORY_GENICAM = pathlib.Path(genicam.__file__).parent
GENICAM_CTI = DIRECTORY_GENICAM / "TLSimu.cti"
assert GENICAM_CTI.exists()


class CameraBase:
    ACQUIRER_QUERY: dict(model="a2A1920-160ucPRO") = None
    FRAME_PER_S: float = None
    FILENAME_CTI: pathlib.Path = None

    @overload
    def configure(self, ia: ImageAcquirer) -> None:
        pass


class CameraBasler(CameraBase):
    ACQUIRER_QUERY = dict(model="a2A1920-160ucPRO")  # Basler
    FRAME_PER_S = 10.0
    FILENAME_CTI = pathlib.Path(
        r"C:\Program Files\Basler\pylon 6\Runtime\x64\ProducerU3V.cti"
    )

    def configure(self, ia: ImageAcquirer) -> None:
        node_map = ia.remote_device.node_map
        # ia.remote_device.node_map.PixelFormat.value = 'Mono8'
        # ia.remote_device.node_map.PixelFormat.value = 'RGB8'
        # ia.remote_device.node_map.PixelFormat.value = 'BayerRG8'
        # ia.remote_device.node_map.PixelFormat.value = pfnc.BayerRG8
        node_map.AcquisitionMode.value = "Continuous"
        node_map.AcquisitionFrameRate.value = self.FRAME_PER_S  # 1/s
        node_map.AcquisitionFrameRateEnable.value = True
        # map.TriggerMode.value ='RGB8'
        node_map.ExposureTime.value = 10000
        print(node_map.PixelFormat.value)
        if node_map.PixelFormat.value != "RGB8":
            access_mode = node_map.PixelFormat.get_access_mode()
            if access_mode in (genapi.EAccessMode.WO, genapi.EAccessMode.RW):
                node_map.PixelFormat.value = "RGB8"
            else:
                print("****************************** COULD NOT SET PixelFormat !!!")
            print(node_map.PixelFormat.value)


class CameraSimulation(CameraBase):
    ACQUIRER_QUERY = dict(serial_number="SN_InterfaceA_1")  # Simulation
    FRAME_PER_S = 10.0
    FILENAME_CTI = GENICAM_CTI

    def configure(self, ia: ImageAcquirer) -> None:
        pass


CAMERAS = [CameraBasler, CameraSimulation]
