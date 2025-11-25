import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Rectangle {
    id: rectangle
    signal videoFileSelected(string path)
    signal openPreview()
    width: 580
    height: 380
    color: "#1e5631ff"
    border.color: "#120606"

    FileDialog {
        id: videoDialog
        title: "Wybierz plik wideo"
        nameFilters: [
            "Pliki wideo (*.mp4 *.avi *.mkv)",
            "Wszystkie pliki (*)"
        ]
        onAccepted: {
            backend.setVideoPath(selectedFile)
            rectangle.videoFileSelected(selectedFile)
        }

    }

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
                text: "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\">\n<html><head><meta name=\"qrichtext\" content=\"1\" /><meta charset=\"utf-8\" /><style type=\"text/css\">\np, li { white-space: pre-wrap; }\nhr { height: 1px; border-width: 0; }\nli.unchecked::marker { content: \"\\2610\"; }\nli.checked::marker { content: \"\\2612\"; }\n</style></head><body style=\" font-family:'Noto Sans'; font-size:9pt; font-weight:400; font-style:normal;\">\n<p align=\"center\" style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Noto Sans'; font-size:24pt; font-weight:700; font-style:italic;\">Upuść tutaj <br />plik wideo!</span></p></body></html>"
                font.pixelSize: 30
                textFormat: Text.RichText
                rotation: 0
                font.styleName: "Bold Italic"
                font.bold: true
                font.weight: Font.DemiBold
            }
        }
        DropArea {
            id: videoDropArea
            anchors.fill: parent
            keys: ["text/uri-list"]

            onEntered: function(drag) {
                tODoDropWhite1.opacity = 0.8
            }

            onExited: function(drag) {
                tODoDropWhite1.opacity = 1.0
            }

            onDropped: function(drop) {
                tODoDropWhite1.opacity = 1.0

                if (drop.hasUrls && drop.urls.length > 0) {
                    var url = drop.urls[0]
                    console.log("[QML] Drop video:", url)
                    backend.setVideoPath(url)
                    rectangle.videoFileSelected(url)  // to samo co przy FileDialog
                    drop.acceptProposedAction()
                }
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

        // Button {
        //     id: button2
        //     x: 31
        //     y: 234
        //     width: 154
        //     height: 52
        //     text: qsTr("Pomoc")
        //
        //     background: Rectangle {
        //         radius: 10
        //         color: "#f3f4f6"
        //         border.width: 2
        //         border.color: "#dfe6dc"
        //     }
        //
        //     contentItem: Text {
        //         text: button2.text
        //         color: "#0d2512"
        //         horizontalAlignment: Text.AlignHCenter
        //         verticalAlignment: Text.AlignVCenter
        //         font.pixelSize: 15
        //         font.bold: true
        //     }
        //
        //     hoverEnabled: true
        //     onHoveredChanged: {
        //         background.color = hovered ? "#ffffff" : "#f3f4f6"
        //     }
        // }


        Button {
            id: loadButton
            x: 31
            y: 110
            width: 154
            height: 52
            text: qsTr("Wczytaj wideo")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: loadButton.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 15
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                        videoDialog.open()
                    }

        }


        Button {
            id: button_analyze
            x: 31
            y: 180
            width: 154
            height: 52
            text: qsTr("Analiza/replay")
            onClicked: {
                rectangle.openPreview()
            }
            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: button_analyze.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 15
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
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

    Image {
        id: image
        x: -20
        y: -20
        width: 169
        height: 131
        source: "../assets/gui_files/image.png"
        fillMode: Image.PreserveAspectFit
    }
    states: [
        State {
            name: "clicked"
        }
    ]
}
