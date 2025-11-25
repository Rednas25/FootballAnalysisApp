import QtQuick
import QtQuick.Controls

Rectangle {
    id: rectangle
    width: 580
    height: 380
    color: "#1e5631ff"
    border.color: "#120606"

    property int currentFrame: 0
    property int totalFrames: 0

    Rectangle {
        id: rectangle1
        x: 204
        y: 0
        width: 376
        height: 380
        opacity: 1
        color: "#1e5631"
        border.width: 0

        Image {
            id: tODoDropWhite1
            x: -470
            y: -84
            width: 1165
            height: 548
            source: "../assets/gui_files/tło do drop(white).svg"
            rotation: 0
            fillMode: Image.PreserveAspectFit

            Text {
                id: text2
                x: 433
                y: 230
                width: 300
                height: 75
                color: "#ffffff"
                text: "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\">\n<html><head><meta name=\"qrichtext\" content=\"1\" /><meta charset=\"utf-8\" /><style type=\"text/css\">\np, li { white-space: pre-wrap; }\nhr { height: 1px; border-width: 0; }\nli.unchecked::marker { content: \"\\2610\"; }\nli.checked::marker { content: \"\\2612\"; }\n</style></head><body style=\" font-family:'Noto Sans'; font-size:9pt; font-weight:400; font-style:normal;\">\n<p align=\"center\" style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Noto Sans'; font-size:24pt; font-weight:700; font-style:italic;\">Trwa <br />Analiza...</span></p></body></html>"
                font.pixelSize: 30
                textFormat: Text.RichText
                rotation: 0
                font.styleName: "Bold Italic"
                font.bold: true
                font.weight: Font.DemiBold
            }
        }
    }

    Rectangle {
        id: rectangle2
        x: 0
        y: 0
        width: 206
        height: 380
        gradient: Gradient {
            GradientStop {
                position: 0
                color: "#0e301a"
            }

            GradientStop {
                position: 1
                color: "#1e5631"
            }
            orientation: Gradient.Horizontal
        }

        // GÓRNY PRZYCISK – Podgląd YOLO
        Button {
            id: yoloPreviewButton
            x: 31
            y: 97
            width: 154
            height: 52
            text: qsTr("Podgląd YOLO")
            checkable: true

            background: Rectangle {
                id: bgYolo
                radius: 10
                color: yoloPreviewButton.checked ? "#ffffff" : "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: yoloPreviewButton.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 15
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                bgYolo.color = hovered || yoloPreviewButton.checked ? "#ffffff" : "#f3f4f6"
            }

            onToggled: {
                // tu podłączasz logikę podglądu YOLO
                backend.setYoloPreview(checked)
            }
        }

        // ŚRODKOWY PRZYCISK – Podgląd mapy 2D
        Button {
            id: minimapPreviewButton
            x: 31
            y: 164
            width: 154
            height: 52
            text: qsTr("Podgląd mapy 2D")
            checkable: true

            background: Rectangle {
                id: bgMinimap
                radius: 10
                color: minimapPreviewButton.checked ? "#ffffff" : "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: minimapPreviewButton.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 15
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                bgMinimap.color = hovered || minimapPreviewButton.checked ? "#ffffff" : "#f3f4f6"
            }

            onToggled: {
                // tu podłączasz logikę podglądu minimapy 2D
                backend.setMinimapPreview(checked)
            }
        }

        // DOLNY PRZYCISK – Zakończ analizę
        Button {
            id: stopButton
            x: 31
            y: 234
            width: 154
            height: 52
            text: qsTr("Zakończ analizę")

            background: Rectangle {
                id: bgStop
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: stopButton.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 15
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                bgStop.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.stopAnalysis()
            }
        }

        Text {
            id: text1
            x: 8
            y: 356
            color: "#ffffff"
            text: qsTr("Autor: Kacper Sieczko")
            font.pixelSize: 12
            font.italic: true
            font.weight: Font.DemiBold
        }
    }

    Column {
        id: column
        x: 0
        y: 0
        width: 206
        height: 380
    }

    // LOGO w tym samym miejscu co w Main_screen
    Image {
        id: image
        x: -20
        y: -20
        width: 169
        height: 131
        source: "../assets/gui_files/image.png"
        fillMode: Image.PreserveAspectFit
    }

    // PROGRESSBAR – zostaje na tej wysokości
    ProgressBar {
        id: progressBar
        x: 100
        y: 300
        width: 400
        height: 25
        to: 100
        value: 0
        z: 0
    }

    Text {
        id: frameInfo
        anchors.horizontalCenter: progressBar.horizontalCenter
        anchors.bottom: progressBar.top
        anchors.bottomMargin: 8
        color: "#ffffff"
        font.pixelSize: 18
        text: "Klatka: " + rectangle.currentFrame + " / " + rectangle.totalFrames
        visible: rectangle.totalFrames > 0
        font.bold: true
    }

    Connections {
        target: backend

        function onAnalysisProgress(pct) {
            progressBar.value = pct
        }

        function onAnalysisFinished() {
            progressBar.value = 100
        }

        function onAnalysisFrameInfo(current, total) {
            rectangle.currentFrame = current;
            rectangle.totalFrames = total;
        }
    }

    states: [
        State {
            name: "clicked"
        }
    ]
}
