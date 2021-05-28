import os

MAX_STRING_SIZE = 1024
SHORT_STRING_SIZE = 256
MAX_KEY_BINDINGS = 50
MAX_RELATION_TARGETS = 25
MAX_RELATIONS = 5
MAX_ACTION_INFO = 256
MAX_ACTIONS_TO_DO = 32
TIMEOUT = 30

# set JAB dll
JDK_BRIDGE_DLL = (
    os.environ.get("JAVA_HOME", ".\\") + "\\jre\\bin\\WindowsAccessBridge-32.dll"
)
JAB_BRIDGE_DLL = os.environ.get("JAB_HOME", ".\\") + "\\WindowsAccessBridge-32.dll"

#: The path to the user's .accessibility.properties file, used
#: to enable JAB.
A11Y_PROPS_PATH = os.path.expanduser(r"~\.accessibility.properties")
#: The content of ".accessibility.properties" when JAB is enabled.
A11Y_PROPS_CONTENT = (
    "assistive_technologies=com.sun.java.accessibility.AccessBridge\n"
    "screen_magnifier_present=true\n"
)
