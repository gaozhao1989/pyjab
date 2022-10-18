from pyjab.jabdriver import JABDriver


class TestBridgeDll(object):
    def test_bridge_default(self, java_control_app) -> None:
        assert java_control_app

    def test_bridge_x86(self) -> None:
        # JDK 1.8
        jabdriver = JABDriver(
            title="Java Control Panel",
            dll=r"C:\Program Files (x86)\Java\jdk8\jre\bin\WindowsAccessBridge-32.dll",
        )
        assert jabdriver

    def test_bridge_x64(self) -> None:
        # JDK 1.8
        jabdriver = JABDriver(
            title="Java Control Panel",
            dll=r"C:\Program Files\Java\jdk8\jre\bin\WindowsAccessBridge-64.dll",
        )
        assert jabdriver

    def test_openjdk(self) -> None:
        # OpenJDK 16
        jabdriver = JABDriver(
            title="Java Control Panel",
            dll=r"C:\Users\garygao\scoop\apps\openjdk16\16.0.2-7\bin\windowsaccessbridge-64.dll",
        )
        assert jabdriver

    def test_jab(self) -> None:
        # JAB 2.0.2
        jabdriver = JABDriver(
            title="Java Control Panel",
            dll=r"C:\Users\garygao\AppData\Local\Programs\accessbridge-2_0_2-fcs-bin-b06\accessbridge2_0_2\WindowsAccessBridge-64.dll",
        )
        assert jabdriver
