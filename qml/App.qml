import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true

    width: 580
    height: 380
    minimumWidth: 580
    minimumHeight: 380
    maximumWidth: 580
    maximumHeight: 380

    title: "AnalizaMeczu"

    Loader {
        id: mainLoader
        anchors.fill: parent
        source: "Main_screen.ui.qml"
    }

    Connections {
        target: mainLoader.item

        // Po wybraniu wideo -> ekran 2 (team selector)
        function onVideoFileSelected(path) {
            root.visibility = Window.Windowed
            root.minimumWidth = 580
            root.minimumHeight = 380
            root.maximumWidth = 580   // zablokuj zmianę rozmiaru
            root.maximumHeight = 380
            root.width = 580
            root.height = 380
            mainLoader.source = "screen2_(teamselector).ui.qml"
        }

        // Ekran 3 (loading screen)
        function onStartAnalysis() {
            root.visibility = Window.Windowed
            root.minimumWidth = 580
            root.minimumHeight = 380
            root.maximumWidth = 580
            root.maximumHeight = 380
            root.width = 580
            root.height = 380
            mainLoader.source = "screen3_loading.ui.qml"
        }

        // Ekran 4 (podgląd) -> większe okno + możliwość zmiany rozmiaru
        function onOpenPreview() {
            root.minimumWidth = 1024
            root.minimumHeight = 576
            root.maximumWidth = 16777215
            root.maximumHeight = 16777215

            // startowy rozmiar
            root.width = 1280
            root.height = 720
            root.visibility = Window.Maximized

            mainLoader.source = "screen4_preview.ui.qml"
        }
        function onBackToMenu() {
            root.visibility = Window.Windowed
            root.minimumWidth = 580
            root.minimumHeight = 380
            root.maximumWidth = 580
            root.maximumHeight = 380
            root.width = 580
            root.height = 380
            mainLoader.source = "Main_screen.ui.qml"
        }

    }

    Connections {
        target: backend
        function onAnalysisFinishedWithDir(dirPath) {
            root.minimumWidth = 1024
            root.minimumHeight = 576
            root.maximumWidth = 16777215
            root.maximumHeight = 16777215
            root.width = 1280
            root.height = 720
            root.visibility = Window.Maximized

            mainLoader.source = "screen4_preview.ui.qml"
            if (dirPath && dirPath.length > 0) {
                var url = "file:///" + dirPath.replace(/\\/g, "/")
                backend.setReplayDirectory(url)
            }
        }
    }


    // F11: przełączanie między Maximized, a FullScreen
    Shortcut {
        sequence: "F11"
        onActivated: {
            if (root.visibility === Window.FullScreen) {
                root.visibility = Window.Maximized
            } else {
                root.visibility = Window.FullScreen
            }
        }
    }
}
