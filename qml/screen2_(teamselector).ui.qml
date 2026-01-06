import QtQuick
import QtQuick.Controls


Rectangle {
    id: rectangle
    width: 580
    height: 380
    signal startAnalysis()
    signal backToMenu()
    color: "#1e5631ff"
    border.color: "#120606"

    Rectangle {
        id: rectangle1
        x: 203
        y: 0
        width: 377
        height: 380
        opacity: 1
        color: "#1e5631"
        border.width: 0
    }

    Rectangle {
        id: rectangle2
        x: -1
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

        Text {
            id: text1
            x: 8
            y: 356
            color: "#ffffff"
            text: qsTr("Made By: Kacper Sieczko")
            font.pixelSize: 12
            font.italic: true
            font.weight: Font.DemiBold
        }
    }

    Image {
        id: image
        x: -20
        y: -13
        width: 115
        height: 86
        source: "../assets/gui_files/image.png"
        fillMode: Image.PreserveAspectFit
    }

    Text {
        id: text2
        x: 160
        y: 8
        width: 144
        height: 32
        color: "#ffffff"
        text: qsTr("Wybierz kolory drużyn")
        font.pixelSize: 25
        font.italic: true
        font.weight: Font.DemiBold
    }

Column {
    id: runNameAndStart
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 30
    spacing:10

    Button {
        id: startButton
        text: qsTr("Rozpocznij Analizę")
        width: 200
        height: 50

        background: Rectangle {
            radius: 10
            color: "#f3f4f6"
            border.width: 2
            border.color: "#dfe6dc"
        }

        contentItem: Text {
            text: startButton.text
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
            backend.startAnalysis(runNameField.text)
            rectangle.startAnalysis()
        }
    }

    TextField {
        id: runNameField
        width: 200
        height: 20
        placeholderText: qsTr("Wprowadź nazwę dla swojej analizy")
        horizontalAlignment: Text.AlignHCenter
    }

}

    Column {
        id: column1
        x: 392
        y: 52
        width: 160
        height: 302

        TextInput {
            id: textInput
            width: 160
            height: 20
            color: "#ffffff"
            text: qsTr("Drużyna B")
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.DemiBold
            cursorVisible: false
        }

        Button {
            id: team_b_player_color
            x: 0
            width: 160
            height: 40
            text: qsTr("Kolor zawodnika")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: team_b_player_color.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.selectTeamBPlayerColor()
            }
        }

        Row {
            id: rectangle4
            width: 160
            height: 50
            spacing: 0

            Rectangle {
                id: rectB1
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.right: parent.right; width: 10; height: parent.height; color: parent.color }
            }
            Rectangle {
                id: rectB2
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.left: parent.left; width: 10; height: parent.height; color: parent.color }
            }
        }
        Rectangle {
            width: 1
            height: 10
            opacity: 0
        }

        Button {
            id: team_b_gk_color_button
            width: 160
            height: 40
            text: qsTr("Kolor Bramkarza")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: team_b_gk_color_button.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.selectTeamBGKColor()
            }
        }


        Row {
            id: rectangle4_gk
            width: 160
            height: 50
            spacing: 0

            Rectangle {
                id: rectBGK1
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.right: parent.right; width: 10; height: parent.height; color: parent.color }
            }
            Rectangle {
                id: rectBGK2
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.left: parent.left; width: 10; height: parent.height; color: parent.color }
            }
        }


    }

    Column {
        id: column2
        x: 203
        y: 52
        width: 160
        height: 302

        TextInput {
            id: textInput1
            width: 160
            height: 20
            color: "#ffffff"
            text: qsTr("Sędzia")
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.DemiBold
            cursorVisible: false
        }

        Button {
            id: referee_color_button
            x: 0
            width: 161
            height: 40
            text: qsTr("Kolor sędziego")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: referee_color_button.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.selectRefereeColor()
            }
        }


        Row {
            id: rectangle5
            width: 160
            height: 50
            spacing: 0

            Rectangle {
                id: rectR1
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.right: parent.right; width: 10; height: parent.height; color: parent.color }
            }
            Rectangle {
                id: rectR2
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.left: parent.left; width: 10; height: parent.height; color: parent.color }
            }
        }
    }

    Column {
        id: column3
        x: 15
        y: 52
        width: 160
        height: 302

        TextInput {
            id: textInput2
            width: 160
            height: 20
            color: "#ffffff"
            text: qsTr("Drużyna A")
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.DemiBold
            cursorVisible: false
            selectionColor: "#000064"
        }

        Button {
            id: team_a_color_button
            x: 0
            width: 160
            height: 40
            text: qsTr("Kolor zawodnika")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: team_a_color_button.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.selectTeamAPlayerColor()
            }
        }


        Row {
            id: rectangle3
            width: 160
            height: 50
            spacing: 0

            Rectangle {
                id: rectA1
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.right: parent.right; width: 10; height: parent.height; color: parent.color }
            }
            Rectangle {
                id: rectA2
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.left: parent.left; width: 10; height: parent.height; color: parent.color }
            }
        }
        Rectangle {
            width: 1
            height: 10
            opacity: 0
        }

        Button {
            id: team_a_gk_color_button1
            x: 0
            width: 160
            height: 40
            text: qsTr("Kolor Bramkarza")

            background: Rectangle {
                radius: 10
                color: "#f3f4f6"
                border.width: 2
                border.color: "#dfe6dc"
            }

            contentItem: Text {
                text: team_a_gk_color_button1.text
                color: "#0d2512"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
                font.bold: true
            }

            hoverEnabled: true
            onHoveredChanged: {
                background.color = hovered ? "#ffffff" : "#f3f4f6"
            }

            onClicked: {
                backend.selectTeamAGKColor()
            }
        }


         Row {
            id: rectangle3_gk
            width: 160
            height: 50
            spacing: 0

            Rectangle {
                id: rectAGK1
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.right: parent.right; width: 10; height: parent.height; color: parent.color }
            }
            Rectangle {
                id: rectAGK2
                width: parent.width / 2
                height: parent.height
                color: "white"
                radius: 10
                antialiasing: true
                clip: true
                layer.enabled: true
                layer.smooth: true
                border.color: "transparent"
                Rectangle { anchors.left: parent.left; width: 10; height: parent.height; color: parent.color }
            }
        }
    }
    Connections {
        target: backend

        function onRolePreviewColorsChanged(key, colorList) {

            if (key === "teamA_player") {
                rectA1.color = colorList[0]
                rectA2.color = colorList[1]
            }
            else if (key === "teamB_player") {
                rectB1.color = colorList[0]
                rectB2.color = colorList[1]
            }
            else if (key === "referee") {
                rectR1.color = colorList[0]
                rectR2.color = colorList[1]
            }
            else if (key === "teamA_goalkeeper") {
                rectAGK1.color = colorList[0]
                rectAGK2.color = colorList[1]
            }
            else if (key === "teamB_goalkeeper") {
                rectBGK1.color = colorList[0]
                rectBGK2.color = colorList[1]
            }
    }
}


Button {
        id: backToMenuBtn
        text: qsTr("Wróć do menu")
        width: 150
        height: 40

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 16
        anchors.bottomMargin: 16

        background: Rectangle {
            radius: 10
            color: "#f3f4f6"
            border.width: 2
            border.color: "#dfe6dc"
        }

        contentItem: Text {
            text: backToMenuBtn.text
            color: "#0d2512"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 14
            font.bold: true
        }

        hoverEnabled: true
        onHoveredChanged: {
            background.color = hovered ? "#ffffff" : "#f3f4f6"
        }

        onClicked: rectangle.backToMenu()
    }


    states: [
        State {
            name: "clicked"
        }
    ]
}
