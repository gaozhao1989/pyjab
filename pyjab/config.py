import os

MAX_STRING_SIZE = 1024
SHORT_STRING_SIZE = 256
MAX_KEY_BINDINGS = 50
MAX_RELATION_TARGETS = 25
MAX_RELATIONS = 5
MAX_ACTION_INFO = 256
MAX_ACTIONS_TO_DO = 32
MAX_VISIBLE_CHILDREN = 256
TIMEOUT = 30

# set JAB dll
WAB_DLL = "WindowsAccessBridge-{}.dll"
JDK_BRIDGE_DLL = os.environ.get("JAVA_HOME", ".") + f"\\jre\\bin\\{WAB_DLL}"
JRE_BRIDGE_DLL = os.environ.get("JRE_HOME", ".") + f"\\bin\\{WAB_DLL}"
JAB_BRIDGE_DLL = os.environ.get("JAB_HOME", ".") + f"\\{WAB_DLL}"

#: The path to the user's .accessibility.properties file, used
#: to enable JAB.
A11Y_PROPS_PATH = os.path.expanduser(r"~\.accessibility.properties")
#: The content of ".accessibility.properties" when JAB is enabled.
A11Y_PROPS_CONTENT = (
    "assistive_technologies=com.sun.java.accessibility.AccessBridge\n"
    "screen_magnifier_present=true\n"
)
