import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Rectangle {
    id: root
    width: Constants.width
    height: Constants.height
    color: "Black"
    signal backToMenu()

    property real selectionStart: 0.0
    property real selectionEnd: 1.0

    // --- Dialog wybierania katalogu z Outputów ---
    FolderDialog {
        id: outputDirDialog
        title: qsTr("Select analysis folder (Outputs)")

        onVisibleChanged: {
            if (visible) {
                var rootPath = backend.getOutputsRoot()
                if (rootPath && rootPath.length > 0) {
                    currentFolder = "file:///" + rootPath
                }
            }
        }

        onAccepted: {
            if (selectedFolder) {
                var url = selectedFolder.toString()
                console.log("[QML] Selected replay dir:", url)
                backend.setReplayDirectory(url)
            }
        }
    }

    // --- Pasek narzędzi na górze ---
    ToolBar {
        id: toolBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 50
        z: 2
        background: Rectangle {
            color: "#102030"
        }

        Row {
            id: toolbarRow
            anchors.fill: parent
            anchors.margins: 0
            spacing: 8
            padding: 8
            anchors.verticalCenter: parent.verticalCenter

            // --- Load ---
            ToolButton {
                id: loadButton
                text: qsTr("Wczytaj")
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 90

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: loadButton.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onClicked: outputDirDialog.open()
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Pitch KP ---
ToolButton {
    id: pitchButton
    text: qsTr("PK Boiska")
    checkable: true
    checked: true
    anchors.verticalCenter: parent.verticalCenter
    implicitWidth: 90

    background: Rectangle {
        radius: 4
        color: pitchButton.checked ? "#275072" : "#1a3a5a"
        border.color: "#3d5a7a"
        border.width: pitchButton.checked ? 2 : 1
    }

    contentItem: Text {
        text: pitchButton.text
        color: "white"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        font.pixelSize: 14
    }

    onClicked: backend.setShowKeypoints(checked)
}


            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Triangles ---
            ToolButton {
                id: trianglesBtn
                text: qsTr("Wskaźniki")
                checkable: true
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 110

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: trianglesBtn.checked ? 2 : 1
                }

                contentItem: Text {
                    text: trianglesBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onToggled: trianglesPanel.visible = checked
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Labels ---
            ToolButton {
                id: labelsBtn
                text: qsTr("Etykiety")
                checkable: true
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 90

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: labelsBtn.checked ? 2 : 1
                }

                contentItem: Text {
                    text: labelsBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onToggled: labelsPanel.visible = checked
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- 2D Map ---
            ToolButton {
                id: map2dBtn
                text: qsTr("Mapa 2D")
                checkable: true
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 100

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: map2dBtn.checked ? 2 : 1
                }

                contentItem: Text {
                    text: map2dBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onClicked: {
                    backend.setReplayMinimapEnabled(checked)
                }
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Selected range tekst ---
            Text {
                id: selectedRangeText
                text: "Zakres klatek: "
                      + backend.selectionStartFrame
                      + " - "
                      + backend.selectionEndFrame
                color: "white"
                font.pixelSize: 13
                verticalAlignment: Text.AlignVCenter
                anchors.verticalCenter: parent.verticalCenter
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Average positions ---
            ToolButton {
                id: avgBtn
                text: qsTr("Średnie pozycje")
                checkable: true
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 150

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: avgBtn.checked ? 2 : 1
                }

                contentItem: Text {
                    text: avgBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onToggled: avgPanel.visible = checked
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Heatmaps ---
            ToolButton {
                id: homographyBtn
                text: qsTr("Mapy cieplne")
                checkable: true
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 130

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: homographyBtn.checked ? 2 : 1
                }

                contentItem: Text {
                    text: homographyBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onToggled: homPanel.visible = checked
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            // --- Backward 48 frames (<<) ---
            ToolButton {
                id: back48Button
                text: qsTr("<<")
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 60

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: back48Button.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onClicked: backend.skipReplayFrames(-48)
            }

            // --- Play / Stop ---
            ToolButton {
                id: playButton
                text: qsTr("Start / Stop")
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 110

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: playButton.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onClicked: backend.toggleReplayAuto()
            }

            // --- Forward 48 frames (>>) ---
            ToolButton {
                id: fwd48Button
                text: qsTr(">>")
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 60

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: fwd48Button.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }

                onClicked: backend.skipReplayFrames(48)
            }

            ToolSeparator {
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 0.7
            }

            ToolButton {
                id: backToMenuBtn
                text: qsTr("Wróć")
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 130
                onClicked: root.backToMenu()

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: backToMenuBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.pixelSize: 14
                }
            }


        }

    }

    // --- Obraz podglądu ---
    Image {
        id: previewImage
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 0

        fillMode: Image.PreserveAspectFit
        cache: false
        asynchronous: false

        source: backend.replayFramePath
    }

    // --- Panel filtrów dla trójkątów (dropdown pod przyciskiem) ---
    Rectangle {
        id: trianglesPanel
        width: 200
        color: "#102030"
        radius: 6
        visible: false
        z: 10

        property int marginTop: 4

        x: toolBar.x + toolbarRow.x + trianglesBtn.x
        y: toolBar.height + marginTop
        height: triColumn.implicitHeight + 16

        Column {
            id: triColumn
            anchors.fill: parent
            anchors.margins: 8
            spacing: 4

            CheckBox {
                id: triTeamA
                text: qsTr("Drużyna A")
                checked: true
                leftPadding: 22
                onToggled: backend.setTrianglesFilter(checked, triTeamB.checked, triRef.checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: triTeamA.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: triTeamA.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            CheckBox {
                id: triTeamB
                text: qsTr("Drużyna B")
                checked: true
                leftPadding: 22
                onToggled: backend.setTrianglesFilter(triTeamA.checked, checked, triRef.checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: triTeamB.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: triTeamB.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            CheckBox {
                id: triRef
                text: qsTr("Sędzia")
                checked: true
                leftPadding: 22
                onToggled: backend.setTrianglesFilter(triTeamA.checked, triTeamB.checked, checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: triRef.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: triRef.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }
        }
    }

    // --- Panel filtrów dla labeli (dropdown pod przyciskiem) ---
    Rectangle {
        id: labelsPanel
        width: 200
        color: "#102030"
        radius: 6
        visible: false
        z: 10

        property int marginTop: 4

        x: toolBar.x + toolbarRow.x + labelsBtn.x
        y: toolBar.height + marginTop
        height: labColumn.implicitHeight + 16

        Column {
            id: labColumn
            anchors.fill: parent
            anchors.margins: 8
            spacing: 4

            CheckBox {
                id: labTeamA
                text: qsTr("Drużyna A")
                checked: true
                leftPadding: 22
                onToggled: backend.setLabelsFilter(checked, labTeamB.checked, labRef.checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: labTeamA.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: labTeamA.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            CheckBox {
                id: labTeamB
                text: qsTr("Drużyna B")
                checked: true
                leftPadding: 22
                onToggled: backend.setLabelsFilter(labTeamA.checked, checked, labRef.checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: labTeamB.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: labTeamB.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            CheckBox {
                id: labRef
                text: qsTr("Sędzia")
                checked: true
                leftPadding: 22
                onToggled: backend.setLabelsFilter(labTeamA.checked, labTeamB.checked, checked)

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: labRef.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: labRef.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }
        }
    }

    // --- Panel Average positions (dropdown pod przyciskiem) ---
    Rectangle {
        id: avgPanel
        width: 220
        color: "#102030"
        radius: 6
        visible: false
        z: 10

        property int marginTop: 4

        x: toolBar.x + toolbarRow.x + avgBtn.x
        y: toolBar.height + marginTop
        height: avgColumn.implicitHeight + 16

        Column {
            id: avgColumn
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            CheckBox {
                id: avgTeamA
                text: qsTr("Drużyna A")
                checked: true
                leftPadding: 22

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: avgTeamA.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: avgTeamA.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            CheckBox {
                id: avgTeamB
                text: qsTr("Drużyna B")
                checked: true
                leftPadding: 22

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    radius: 3
                    border.width: 1
                    border.color: "white"
                    color: avgTeamB.checked ? "#29a329" : "transparent"
                }

                contentItem: Text {
                    text: avgTeamB.text
                    color: "white"
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13
                }
            }

            Button {
                id: avgGenerateBtn
                text: qsTr("Generuj")
                anchors.horizontalCenter: parent.horizontalCenter

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: avgGenerateBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 14
                }
                onClicked: {
                    backend.generateAveragePositions(avgTeamA.checked, avgTeamB.checked)
                }
            }
        }
    }

    // --- Panel Heatmaps (dropdown pod przyciskiem) ---
    Rectangle {
        id: homPanel
        width: 360
        color: "#102030"
        radius: 6
        visible: false
        z: 10

        property int marginTop: 4
        property var teamAChecks: []
        property var teamBChecks: []

        x: toolBar.x + toolbarRow.x + homographyBtn.x
        y: toolBar.height + marginTop
        height: homColumn.implicitHeight + 16

        Column {
            id: homColumn
            anchors.fill: parent
            anchors.margins: 8
            spacing: 8

            Row {
                id: homRow
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 24

                // --- TEAM A ---
                Column {
                    spacing: 4
                    Text {
                        text: qsTr("Drużyna A")
                        color: "white"
                        font.pixelSize: 13
                        font.bold: true
                    }

                    Repeater {
                        model: 11
                        delegate: CheckBox {
                            id: teamAPlayerCheck
                            property int playerNumber: index + 1
                            text: playerNumber.toString()
                            checked: false
                            leftPadding: 22

                            Component.onCompleted: {
                                homPanel.teamAChecks.push(teamAPlayerCheck)
                            }

                            indicator: Rectangle {
                                implicitWidth: 16
                                implicitHeight: 16
                                radius: 3
                                border.width: 1
                                border.color: "white"
                                color: checked ? "#29a329" : "transparent"
                            }

                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                // --- TEAM B ---
                Column {
                    spacing: 4
                    Text {
                        text: qsTr("Drużyna B")
                        color: "white"
                        font.pixelSize: 13
                        font.bold: true
                    }

                    Repeater {
                        model: 11
                        delegate: CheckBox {
                            id: teamBPlayerCheck
                            property int playerNumber: index + 1
                            text: playerNumber.toString()
                            checked: false
                            leftPadding: 22

                            Component.onCompleted: {
                                homPanel.teamBChecks.push(teamBPlayerCheck)
                            }

                            indicator: Rectangle {
                                implicitWidth: 16
                                implicitHeight: 16
                                radius: 3
                                border.width: 1
                                border.color: "white"
                                color: checked ? "#29a329" : "transparent"
                            }

                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                // --- GROUP ---
                Column {
                    spacing: 4
                    Text {
                        text: qsTr("Grupy")
                        color: "white"
                        font.pixelSize: 13
                        font.bold: true
                    }

                    CheckBox {
                        id: groupTeamA
                        text: qsTr("Drużyna A")
                        checked: false
                        leftPadding: 22

                        indicator: Rectangle {
                            implicitWidth: 16
                            implicitHeight: 16
                            radius: 3
                            border.width: 1
                            border.color: "white"
                            color: groupTeamA.checked ? "#29a329" : "transparent"
                        }

                        contentItem: Text {
                            text: groupTeamA.text
                            color: "white"
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: 12
                        }
                    }

                    CheckBox {
                        id: groupTeamB
                        text: qsTr("Drużyna B")
                        checked: false
                        leftPadding: 22

                        indicator: Rectangle {
                            implicitWidth: 16
                            implicitHeight: 16
                            radius: 3
                            border.width: 1
                            border.color: "white"
                            color: groupTeamB.checked ? "#29a329" : "transparent"
                        }

                        contentItem: Text {
                            text: groupTeamB.text
                            color: "white"
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: 12
                        }
                    }

                    CheckBox {
                        id: groupAllPlayers
                        text: qsTr("Wszyscy zawodnicy")
                        checked: false
                        leftPadding: 22

                        indicator: Rectangle {
                            implicitWidth: 16
                            implicitHeight: 16
                            radius: 3
                            border.width: 1
                            border.color: "white"
                            color: groupAllPlayers.checked ? "#29a329" : "transparent"
                        }

                        contentItem: Text {
                            text: groupAllPlayers.text
                            color: "white"
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: 12
                        }
                    }
                }

            }

            Button {
                id: homGenerateBtn
                text: qsTr("Generuj")
                anchors.horizontalCenter: parent.horizontalCenter

                background: Rectangle {
                    radius: 4
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: homGenerateBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 14
                }

                onClicked: {
                    var selA = []
                    for (var i = 0; i < homPanel.teamAChecks.length; ++i) {
                        var cbA = homPanel.teamAChecks[i]
                        if (cbA && cbA.checked)
                            selA.push(cbA.playerNumber)
                    }

                    var selB = []
                    for (var j = 0; j < homPanel.teamBChecks.length; ++j) {
                        var cbB = homPanel.teamBChecks[j]
                        if (cbB && cbB.checked)
                            selB.push(cbB.playerNumber)
                    }

                    console.log("[QML] Heatmaps generate, A:", selA, "B:", selB,
                                "groups:", groupTeamA.checked,
                                groupTeamB.checked, groupAllPlayers.checked)

                    backend.generateHeatmaps(
                        selA,
                        selB,
                        groupTeamA.checked,
                        groupTeamB.checked,
                        groupAllPlayers.checked
                    )
                }
            }



        }
    }

    // --- Timeline odtwarzania ---
    Slider {
        id: playbackTimeline
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 16
        height: 24

        from: 0
        to: 1
        value: 0
        enabled: true

        onPressedChanged: {
            if (!pressed) {
                backend.seekReplayToPosition(value)
            }
        }

        background: Rectangle {
            implicitHeight: 4
            radius: 2
            color: "#505050"

            Rectangle {
                width: playbackTimeline.visualPosition * parent.width
                height: parent.height
                radius: 2
                color: "#9090ff"
            }
        }

        handle: Rectangle {
            width: 14
            height: 14
            radius: 7
            color: "#ff4040"
            border.color: "#ffffff"
            border.width: 1

            x: playbackTimeline.visualPosition * (playbackTimeline.width - width)
            y: (playbackTimeline.height - height) / 2

            opacity: playbackTimeline.enabled ? 1.0 : 0.8
        }
    }

    // --- Nakładka zakresu na timeline ---
    Rectangle {
        id: selectionOverlay
        anchors.left: playbackTimeline.left
        anchors.right: playbackTimeline.right
        anchors.top: playbackTimeline.top
        anchors.bottom: playbackTimeline.bottom
        color: "transparent"
        z: playbackTimeline.z + 1

        Rectangle {
            id: selectionFill
            anchors.verticalCenter: parent.verticalCenter
            x: root.selectionStart * parent.width
            width: (root.selectionEnd - root.selectionStart) * parent.width
            height: 6
            radius: 3
            color: "#8000b894"
        }

        Rectangle {
            id: leftHandle
            width: 10
            height: 18
            radius: 3
            color: "#00b894"
            border.color: "white"
            border.width: 1

            x: root.selectionStart * (parent.width - width)
            y: (parent.height - height) / 2

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeHorCursor
                drag.target: parent
                drag.axis: Drag.XAxis
                drag.minimumX: 0
                drag.maximumX: rightHandle.x

                onPositionChanged: {
                    var denom = selectionOverlay.width - parent.width
                    if (denom <= 0) denom = 1
                    root.selectionStart = parent.x / denom
                    if (root.selectionStart < 0.0) root.selectionStart = 0.0
                    if (root.selectionStart > root.selectionEnd) root.selectionStart = root.selectionEnd
                    backend.setSelectionRange(root.selectionStart, root.selectionEnd)
                }
            }
        }

        Rectangle {
            id: rightHandle
            width: 10
            height: 18
            radius: 3
            color: "#00b894"
            border.color: "white"
            border.width: 1

            x: root.selectionEnd * (parent.width - width)
            y: (parent.height - height) / 2

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeHorCursor
                drag.target: parent
                drag.axis: Drag.XAxis
                drag.minimumX: leftHandle.x
                drag.maximumX: selectionOverlay.width - parent.width

                onPositionChanged: {
                    var denom = selectionOverlay.width - parent.width
                    if (denom <= 0) denom = 1
                    root.selectionEnd = parent.x / denom
                    if (root.selectionEnd > 1.0) root.selectionEnd = 1.0
                    if (root.selectionEnd < root.selectionStart) root.selectionEnd = root.selectionStart
                    backend.setSelectionRange(root.selectionStart, root.selectionEnd)
                }
            }
        }
    }

    // --- Pływająca 2D mapka (snapshot boiska, przesuwalna + skalowalna) ---
    Rectangle {
        id: minimapOverlay

        // Rozmiar startowy
        property real userWidth: Math.min(root.width * 0.35, 520)
        property real userHeight: Math.min(root.height * 0.4, 320)

        // Minimalne / maksymalne wymiary
        property real minWidth: 220
        property real minHeight: 140
        property real maxWidth: root.width * 0.9
        property real maxHeight: playbackTimeline.y - toolBar.height - 20

        // Faktyczny width/height
        width: Math.min(Math.max(userWidth, minWidth),  maxWidth)
        height: Math.min(Math.max(userHeight, minHeight), maxHeight)

        x: (root.width - width) / 2
        y: playbackTimeline.y - height - 12

        radius: 10
        color: "#102030"
        border.color: "#3d5a7a"
        border.width: 2
        visible: backend.minimapImagePath !== ""
        z: 15

        Image {
            id: minimapImage
            anchors.fill: parent
            anchors.margins: 10
            source: backend.minimapImagePath
            fillMode: Image.PreserveAspectFit
            cache: false
        }

        MouseArea {
            id: minimapDragArea
            anchors.fill: parent
            cursorShape: Qt.OpenHandCursor

            drag.target: minimapOverlay
            drag.axis: Drag.XAndYAxis

            drag.minimumX: 0
            drag.maximumX: root.width - minimapOverlay.width
            drag.minimumY: toolBar.height
            drag.maximumY: playbackTimeline.y - minimapOverlay.height

            onPressed: cursorShape = Qt.ClosedHandCursor
            onReleased: cursorShape = Qt.OpenHandCursor
        }

        // UCHWYT DO ZMIANY ROZMIARU
        Rectangle {
            id: resizeHandle
            width: 18
            height: 18
            radius: 4
            color: "#1a3a5a"
            border.color: "#a0b0c0"

            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 6
            z: 20

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeBDiagCursor   // ↖ ↘

                property real pressX
                property real pressY
                property real startW
                property real startH

                onPressed: {
                    pressX = mouse.x
                    pressY = mouse.y
                    startW = minimapOverlay.userWidth
                    startH = minimapOverlay.userHeight
                }

                onPositionChanged: {
                    if (!pressed)
                        return

                    var dx = mouse.x - pressX
                    var dy = mouse.y - pressY

                    // szerokość rośnie w prawo
                    minimapOverlay.userWidth = startW + dx
                    // wysokość rośnie w dół → uchwyt u góry, więc minus
                    minimapOverlay.userHeight = startH - dy
                }
            }
        }
    }




    // --- Overlay Average Positions ---
    Rectangle {
        id: avgMapOverlay
        anchors.fill: parent
        color: "#00000080"
        visible: backend.avgPositionsImagePath !== ""
        z: 20

        Rectangle {
            id: avgMapCard
            width: Math.min(parent.width * 0.8, 1000)
            height: Math.min(parent.height * 0.8, 650)
            anchors.centerIn: parent
            color: "#102030"
            radius: 10
            border.color: "#3d5a7a"
            border.width: 2

            Text {
                id: avgTitle
                text: qsTr("Mapa średnich pozycji")
                color: "white"
                font.pixelSize: 26
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 18
            }

            ToolButton {
                id: avgCloseBtn
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 10
                text: "✕"

                background: Rectangle {
                    radius: 10
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: avgCloseBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 16
                }

                onClicked: backend.hideAvgPositionsPreview()
            }

            Image {
                id: avgMapImage
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.top: avgTitle.bottom
                anchors.margins: 24
                source: backend.avgPositionsImagePath
                fillMode: Image.PreserveAspectFit
                cache: false
            }
        }
    }

    // --- Overlay Heatmaps (galeria) ---
    Rectangle {
        id: heatmapOverlay
        anchors.fill: parent
        color: "#00000080"
        visible: backend.heatmapImagePath !== ""
        z: 21

        Rectangle {
            id: heatmapCard
            width: Math.min(parent.width * 0.8, 1000)
            height: Math.min(parent.height * 0.8, 650)
            anchors.centerIn: parent
            color: "#102030"
            radius: 10
            border.color: "#3d5a7a"
            border.width: 2

            Text {
                id: heatmapTitle
                text: qsTr("Mapy cieplne")
                color: "white"
                font.pixelSize: 26
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 16
            }

            ToolButton {
                id: heatmapCloseBtn
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 10
                text: "✕"

                background: Rectangle {
                    radius: 10
                    color: "#1a3a5a"
                    border.color: "#3d5a7a"
                    border.width: 1
                }

                contentItem: Text {
                    text: heatmapCloseBtn.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 16
                }

                onClicked: backend.hideHeatmapPreview()
            }

            Image {
                id: heatmapImage
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: heatmapTitle.bottom
                anchors.bottom: controlsRow.top
                anchors.margins: 24
                source: backend.heatmapImagePath
                fillMode: Image.PreserveAspectFit
                cache: false
            }

            Row {
                id: controlsRow
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 16
                spacing: 24
                height: 40

                Button {
                    id: prevBtn
                    text: "<<"
                    width: 60
                    background: Rectangle {
                        radius: 4
                        color: "#1a3a5a"
                        border.color: "#3d5a7a"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: prevBtn.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                    }
                    onClicked: backend.prevHeatmap()
                }

                Text {
                    id: heatmapLabelText
                    text: backend.heatmapLabel
                    color: "white"
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                Button {
                    id: nextBtn
                    text: ">>"
                    width: 60
                    background: Rectangle {
                        radius: 4
                        color: "#1a3a5a"
                        border.color: "#3d5a7a"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: nextBtn.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                    }
                    onClicked: backend.nextHeatmap()
                }

            }
        }
    }

    Connections {
        target: backend
        function onReplayPositionChanged(pos) {
            if (!playbackTimeline.pressed) {
                playbackTimeline.value = pos
            }
        }
    }

}
