from os import path
from ctypes import (cdll, create_string_buffer)
from typing import (Optional, List)

from .abstract_classes import (Server, AsyncServer, Service)


class DobotServer(Server):
    """Dobotとの通信。

    Attributes:
        Lib: C で定義された元のライブラリ
    """
    _CUR_DIR = path.dirname(path.abspath(__file__))
    Lib = cdll.LoadLibrary(_CUR_DIR + "/libDobotDll.so.1.0.0")

    def __init__(self):
        self._is_connected = False
        self.search = DobotSearcher(self)
        self.connect = DobotConnector(self)
        self.firmware_type = ""
        self.firmware_version = ""
        self.disconnect = DobotDisconnector(self)

    def is_started(self) -> bool:
        return self._is_connected

    # with 文のサポート
    def __enter__(self, port: Optional(str) = None) -> 'DobotServer':
        self.connect(port)
        return self

    def __exit__(self, *_):
        self.disconnect()


class AbstractDobotServer(Server):
    """Dobot に関わる機能群"""
    def __init__(self, dobot: DobotServer):
        self.dobot = dobot

    def is_started(self):
        return self.dobot.is_started()


class AbstractAsyncDobotServer(AsyncServer):
    """Dobot と非同期で何らかの機能を提供するためのクラス"""
    def __init__(self, server: DobotServer):
        self.server = server


class AbstractDobotService(Service):
    """Dobot の1コマンド"""
    def __init__(self, server: DobotServer):
        self.server = server


class DobotSearcher(AbstractDobotService):
    """接続可能な Dobot を検索するコマンド"""
    MAX_LEN = 128

    def __call__(self) -> List[str]:
        """接続可能な Dobot を検索する"""
        buf_result = create_string_buffer(self.MAX_LEN)
        num = self.server.Lib.SearchDobot(buf_result, self.MAX_LEN)
        if num == 0:
            return []
        return buf_result.value.decode("utf-8").split(' ')


class DobotConnector(AbstractDobotService):
    """Dobot と接続するためのコマンド"""
    MAX_STR_LEN = 128

    def __init__(self, server: DobotServer, default_port: str = "", *,
                 encode_type: str = "utf-8", baud_rate: int = 115200):
        """Dobot と接続に関する設定

        Args:
            default_port: 呼び出し時に指定するポートを表す文字列のデフォルト値。
                Dobot が1つしか繋がってない場合は空文字で問題無い。
            encode_type: 入出力に使用する文字列の文字コード。
            baud_rate: ボーレートは通常 115200 固定。
        """
        self.server = server

        self.default_port = default_port
        self.baud_rate = baud_rate
        self.encode_type = encode_type

    def __call__(self, port: Optional(str) = None) -> dict:
        """接続し、ファームウェアの種類とバージョンを返す

        Args:
            port: ポートを表す文字列。DobotSearcher によって得られる文字列配列に含まれるもの。
                  設定しない場合は、初期化時の default_port を参照する。
        Return:
            "firmware_type" と "firmware_version" をキーに持つ dict。
        Raises:
            ConnectionError
        """
        if port is None:
            port = self.default_port

        port_name = create_string_buffer(port.encode(self.encode_type),
                                         self.MAX_STR_LEN)
        fw_type = create_string_buffer(self.MAX_STR_LEN)
        version = create_string_buffer(self.MAX_STR_LEN)

        result = self.server.Lib.ConnectDobot(
            port_name, self.baud_rate, fw_type, version)

        if result == 0:  # No Error
            self.server._is_connected = True
            fw_type = fw_type.value.decode(self.encode_type)
            version = version.value.decode(self.encode_type)
            self.server.firmware_type = fw_type
            self.server.firmware_version = version
            return {
                "firmware_type": fw_type, "firmware_version": version
            }
        elif result == 1:  # Not Found
            raise ConnectionError("Dobot interface was not found.")
        elif result == 2:  # Occupied
            raise ConnectionError(
                "Dobot interface is occupied or unavailable.")
        else:
            raise ConnectionError("Unknown Error with connecting Dobot")


class DobotDisconnector(AbstractDobotService):
    """切断するためのコマンド"""
    def __call__(self) -> None:
        """切断"""
        self.server.API.DisconnectDobot()
        self.server._is_connected = False
        self.server.firmware_type = ""
        self.server.firmware_version = ""
