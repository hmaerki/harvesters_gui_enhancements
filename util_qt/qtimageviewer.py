""" QtImageViewer.py: PyQt image viewer widget for a QPixmap in a QGraphicsView scene with mouse zooming and panning.

"""
import sys
import random
import pathlib

from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QFileDialog, QApplication

__author__ = "Marcel Goldschen-Ohm <marcel.goldschen@gmail.com>"
__version__ = "0.9.0"

# Image aspect ratio mode.
# !!! ONLY applies to full image. Aspect ratio is always ignored when zooming.
#   Qt.IgnoreAspectRatio: Scale image to fit viewport.
#   Qt.KeepAspectRatio: Scale image to fit inside viewport, preserving aspect ratio.
#   Qt.KeepAspectRatioByExpanding: Scale image to fill the viewport, preserving aspect ratio.
_ASPECT_RATIO_MODE = Qt.KeepAspectRatio

_ZOOM_FACTOR = 1.25


class QtImageViewer(QGraphicsView):
    """PyQt image viewer widget for a QPixmap in a QGraphicsView scene with mouse zooming and panning.

    Displays a QImage or QPixmap (QImage is internally converted to a QPixmap).
    To display any other image format, you must first convert it to a QImage or QPixmap.

    Some useful image format conversion utilities:
        qimage2ndarray: NumPy ndarray <==> QImage    (https://github.com/hmeine/qimage2ndarray)
        ImageQt: PIL Image <==> QImage  (https://github.com/python-pillow/Pillow/blob/master/PIL/ImageQt.py)

    Mouse interaction:
        Left mouse button drag: Pan image.
        Right mouse button drag: Zoom box.
        Right mouse button doubleclick: Zoom to show entire image.
    """

    # Mouse button signals emit image scene (x, y) coordinates.
    # !!! For image (row, column) matrix indexing, row = y and column = x.
    leftMouseButtonPressed = pyqtSignal(float, float)
    rightMouseButtonPressed = pyqtSignal(float, float)
    leftMouseButtonReleased = pyqtSignal(float, float)
    rightMouseButtonReleased = pyqtSignal(float, float)
    leftMouseButtonDoubleClicked = pyqtSignal(float, float)
    rightMouseButtonDoubleClicked = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Image is displayed as a QPixmap in a QGraphicsScene attached to this QGraphicsView.
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Store a local handle to the scene's current image pixmap.
        self._pixmapHandle = None

        # Scroll bar behaviour.
        #   Qt.ScrollBarAlwaysOff: Never shows a scroll bar.
        #   Qt.ScrollBarAlwaysOn: Always shows a scroll bar.
        #   Qt.ScrollBarAsNeeded: Shows a scroll bar only when zoomed.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Flags for enabling/disabling mouse interaction.
        self.canZoom = True
        self.canPan = True

        self._is_zooming = False

    def hasPixmap(self):
        """Returns whether or not the scene contains an image pixmap."""
        return self._pixmapHandle is not None

    def clearImage(self):
        """Removes the current image pixmap from the scene if it exists."""
        if self.hasPixmap():
            self.scene.removeItem(self._pixmapHandle)
            self._pixmapHandle = None

    def pixmap(self) -> QPixmap:
        """Returns the scene's current image pixmap as a QPixmap, or else None if no image exists.
        :rtype: QPixmap | None
        """
        if self.hasPixmap():
            return self._pixmapHandle.pixmap()
        return None

    def setImage(self, image: QImage):
        """Set the scene's current image pixmap to the input QImage or QPixmap.
        Raises a RuntimeError if the input image has type other than QImage or QPixmap.
        :type image: QImage | QPixmap
        """
        pixmap = image
        if isinstance(image, QImage):
            pixmap = QPixmap.fromImage(image)
        assert isinstance(pixmap, QPixmap)
        rectBefore = None
        rectNew = QRectF(pixmap.rect())
        if self.hasPixmap():
            rectBefore = self.sceneRect()
            self._pixmapHandle.setPixmap(pixmap)
        else:
            self._pixmapHandle = self.scene.addPixmap(pixmap)
        if rectBefore != rectNew:
            self.setSceneRect(QRectF(pixmap.rect()))  # Set scene size to image size.
            self.updateViewer()

    def loadImageFromFile(self, fileName: pathlib.Path = None):
        """Load an image from file.
        Without any arguments, loadImageFromFile() will popup a file dialog to choose the image file.
        With a fileName argument, loadImageFromFile(fileName) will attempt to load the specified image file directly.
        """
        if fileName is None:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open image file.")
        if isinstance(fileName, str):
            fileName = pathlib.Path(fileName)
        assert isinstance(fileName, pathlib.Path)
        if fileName.is_file():
            image = QImage(str(fileName))
            self.setImage(image)

    def updateViewer(self):
        """Show current zoom (if showing entire image, apply current aspect ratio mode)."""
        if not self.hasPixmap():
            return
        if not self._is_zooming:
            self.fitInView(self.sceneRect(), _ASPECT_RATIO_MODE)

    def resizeEvent(self, event):
        """Maintain current zoom on resize."""
        self.updateViewer()

    def mousePressEvent(self, event):
        """Start mouse pan or zoom mode."""
        scenePos = self.mapToScene(event.pos())
        if event.button() == Qt.LeftButton:
            if self.canPan:
                self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.leftMouseButtonPressed.emit(scenePos.x(), scenePos.y())
        QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """Stop mouse pan or zoom mode (apply zoom if valid)."""
        QGraphicsView.mouseReleaseEvent(self, event)
        scenePos = self.mapToScene(event.pos())
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.leftMouseButtonReleased.emit(scenePos.x(), scenePos.y())
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.rightMouseButtonReleased.emit(scenePos.x(), scenePos.y())

    def mouseDoubleClickEvent(self, event):
        """Show entire image."""
        scenePos = self.mapToScene(event.pos())
        if event.button() == Qt.LeftButton:
            self.leftMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
            if self.canZoom:
                self._is_zooming = False
                self.updateViewer()
        elif event.button() == Qt.RightButton:
            self.rightMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
        QGraphicsView.mouseDoubleClickEvent(self, event)

    def wheelEvent(self, event):
        """
        Zoom in or out of the view.
        https://stackoverflow.com/questions/19113532/qgraphicsview-zooming-in-and-out-under-mouse-position-using-mouse-wheel
        """
        if self.canZoom:
            self._is_zooming = True

            zoom = _ZOOM_FACTOR if event.angleDelta().y() > 0 else 1 / _ZOOM_FACTOR

            self.scale(zoom, zoom)

        QGraphicsView.wheelEvent(self, event)


if __name__ == "__main__":
    def handleLeftClick(x, y):
        print(f"Clicked on image pixel (x={x:0.2f}, y={y:0.2f})")

    # Create the application.
    app = QApplication(sys.argv)

    # Create image viewer and load an image file to display.
    viewer = QtImageViewer()
    #  viewer.loadImageFromFile()  # Pops up file dialog.

    images = []
    for i in range(6):
        filename_png = pathlib.Path(__file__).parent.parent / "images" / f"side{i}.png"
        images.append(QImage(str(filename_png)))

    def random_image():
        viewer.setImage(random.choice(images))

    timer = QTimer(app)
    timer.timeout.connect(random_image)
    timer.start(2000)


    # Handle left mouse clicks with custom slot.
    viewer.leftMouseButtonPressed.connect(handleLeftClick)

    # Show viewer and run application.
    viewer.show()
    sys.exit(app.exec_())
