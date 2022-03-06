import sys
import random
import pathlib

from PyQt5.QtCore import pyqtSignal, QPoint, QSize, Qt, QTimer
from PyQt5.QtGui import (
    QColor,
    QImage,
    QMatrix4x4,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
    QOpenGLVersionProfile,
    QSurfaceFormat,
)
from PyQt5.QtWidgets import QApplication, QGridLayout, QOpenGLWidget, QWidget


_VERTEX_SHADER = """
#version 330 core

// Uniforms
uniform mat4 u_projection;

// Attributes
attribute vec2 a_position;
attribute vec2 a_texcoord;

// Varyings
varying vec2 v_texcoord;

// Main
void main (void)
{
    v_texcoord = a_texcoord;
    gl_Position = u_projection * vec4(a_position, 0.0, 1.0);
}
"""

_FRAGMENT_SHADER = """
#version 330 core

varying vec2 v_texcoord;
uniform sampler2D u_texture;
void main()
{
    gl_FragColor = texture2D(u_texture, v_texcoord);
}
"""


class QHarvestersWidget(QOpenGLWidget):

    clicked = pyqtSignal()

    class ValueBase:
        def __init__(self, program: QOpenGLShaderProgram, name: str):
            assert isinstance(program, QOpenGLShaderProgram)
            assert isinstance(name, str)
            self._program = program
            self._name = name
            self._location = self._get_location()

        def _get_location(self):
            raise NotImplementedError

    class UniformValue(ValueBase):
        def _get_location(self):
            return self._program.uniformLocation(self._name)

        def set(self, value):
            self._program.setUniformValue(self._location, value)

    class AttributeArray(ValueBase):
        def _get_location(self):
            return self._program.attributeLocation(self._name)

        def enableArray(self):
            self._program.enableAttributeArray(self._location)

        def setArray(self, array):
            self._program.setAttributeArray(self._location, array)

    class ProgramValues:
        def __init__(self, program: QOpenGLShaderProgram):
            self.u_projection = QHarvestersWidget.UniformValue(program, "u_projection")
            self.u_texture = QHarvestersWidget.UniformValue(program, "u_texture")
            self.a_texcoord = QHarvestersWidget.AttributeArray(program, "a_texcoord")
            self.a_position = QHarvestersWidget.AttributeArray(program, "a_position")

    def __init__(self, parent=None):
        super(QHarvestersWidget, self).__init__(parent)

        self.clearColor = QColor(Qt.black)

        self._program: QOpenGLShaderProgram = None
        self._values: QHarvestersWidget.ProgramValues = None

        self._last_mouse_dragging_pos = QPoint()
        self._magnification = 1.0
        self._coordinate = [0, 0]
        self._origin = [0, 0]
        self._dirty = True
        self._image = QImage(100, 100, QImage.Format_Indexed8)

        self._width, self._height = 100, 100

        self._texture: QOpenGLTexture = None

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(250, 250)

    def setClearColor(self, color):
        self.clearColor = color
        self.update()

    def setImage(self, image):
        self._image = image
        self.update()

    def setData(self, width: int, height: int, format, data: bytes):
        self.update()

    def initializeGL(self):
        version_profile = QOpenGLVersionProfile()
        version_profile.setVersion(2, 1)
        self._gl = self.context().versionFunctions(version_profile)
        self._gl.initializeOpenGLFunctions()

        self._gl.glDepthFunc(self._gl.GL_LESS)
        self._gl.glEnable(self._gl.GL_CULL_FACE)

        vshader = QOpenGLShader(QOpenGLShader.Vertex, self)
        vshader.compileSourceCode(_VERTEX_SHADER)
        print(f"vshader.log='{vshader.log()}'")

        fshader = QOpenGLShader(QOpenGLShader.Fragment, self)
        fshader.compileSourceCode(_FRAGMENT_SHADER)
        print(f"fshader.log='{fshader.log()}'")

        self._program = QOpenGLShaderProgram()
        self._program.addShader(vshader)
        self._program.addShader(fshader)
        print(f"self._program.log='{self._program.log()}'")

        self._program.link()

        self._values = QHarvestersWidget.ProgramValues(self._program)

        self._program.bind()

        self._values.a_position.enableArray()
        self._values.a_texcoord.enableArray()

        self._values.a_texcoord.setArray(
            [[0.0, 1.0], [1.0, 1.0], [0.0, 0.0], [1.0, 0.0]]
        )

        self._program.release()

    def paintGL(self):
        self._gl.glClearColor(
            self.clearColor.redF(),
            self.clearColor.greenF(),
            self.clearColor.blueF(),
            self.clearColor.alphaF(),
        )
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT | self._gl.GL_DEPTH_BUFFER_BIT)

        if self._image is not None:
            self._width, self._height = self._image.width(), self._image.height()

            if False:
                if self._texture_format != self._image.format():
                    if self._texture is not None:
                        print("Distroyed texture as the image format changed")
                        self._texture.destroy()
                        del self._texture
                        self._texture = None

                if self._texture is None:
                    print(
                        f"{self._image.format()} {self._image.isDetached()} {self._image.colorCount()} {self._image.sizeInBytes()} {self._image.width()}/{self._image.height()}"
                    )
                    self._texture = QOpenGLTexture(self._image)
                    self._texture.setMinificationFilter(
                        QOpenGLTexture.LinearMipMapLinear
                    )
                    self._texture.setMagnificationFilter(QOpenGLTexture.Linear)
                else:
                    print(
                        f"{self._image.format()} {self._image.isDetached()} {self._image.colorCount()} {self._image.sizeInBytes()} {self._image.width()}/{self._image.height()}"
                    )
                    print("vvvvvvvvvvvv")
                    self._texture.setData(
                        self._image, QOpenGLTexture.DontGenerateMipMaps
                    )
                    print("^^^^^^^^^^^^")
                self._texture_format = self._image.format()
            if True:
                if self._texture is not None:
                    # self._texture.destroy()
                    del self._texture
                self._texture = QOpenGLTexture(self._image)
                self._texture.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
                self._texture.setMagnificationFilter(QOpenGLTexture.Linear)

            self._image = None
            self._dirty = True

        if self._texture is None:
            return

        self._program.bind()
        self._recalc_projection()

        self._texture.bind()
        self._gl.glDrawArrays(self._gl.GL_TRIANGLE_STRIP, 0, 4)
        self._texture.release()
        self._program.release()

    def _recalc_projection(self):
        if not self._dirty:
            return
        self._dirty = False

        canvas_w, canvas_h = self.width(), self.height()
        self._gl.glViewport(0, 0, canvas_w, canvas_h)

        #
        w, h = self._width, self._height

        m = QMatrix4x4()
        m.ortho(
            self._coordinate[0],
            canvas_w * self._magnification + self._coordinate[0],
            self._coordinate[1],
            canvas_h * self._magnification + self._coordinate[1],
            -1,
            1,
        )
        self._values.u_projection.set(m)

        x, y = int((canvas_w * self._magnification - w) / 2), int(
            (canvas_h * self._magnification - h) / 2
        )  # centering x & y

        self._values.a_position.setArray(
            [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]
        )

    def resizeGL(self, width, height):
        self._dirty = True

    def wheelEvent(self, event):
        factor = 1.1 if (event.angleDelta().y() > 0) else 0.9
        self._magnification *= factor
        self._dirty = True
        self.update()

    def mousePressEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._last_mouse_dragging_pos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self._last_mouse_dragging_pos.x()
        dy = event.y() - self._last_mouse_dragging_pos.y()

        if event.buttons() & Qt.LeftButton:
            self._coordinate[0] -= int(dx * self._magnification)
            self._coordinate[1] += int(dy * self._magnification)
            self._dirty = True
            self.update()

        self._last_mouse_dragging_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self.clicked.emit()


class Window(QWidget):
    def __init__(self):
        super(Window, self).__init__()

        mainLayout = QGridLayout()

        clearColor = QColor()
        clearColor.setHsv(255, 255, 63)
        clearColor = QColor(Qt.gray)

        widget = QHarvestersWidget()
        widget.setClearColor(clearColor)
        mainLayout.addWidget(widget, 0, 0)

        self.setLayout(mainLayout)

        images = []
        for i in range(6):
            filename_png = pathlib.Path(__file__).parent.parent / "images" / f"side{i}.png"
            images.append(QImage(str(filename_png)))

        def random_image():
            widget.setImage(random.choice(images))

        timer = QTimer(self)
        timer.timeout.connect(random_image)
        timer.start(2000)

        widget.setImage(images[0])
        self.setWindowTitle("Textures")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    format = QSurfaceFormat()
    format.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(format)

    window = Window()
    window.show()
    sys.exit(app.exec_())
