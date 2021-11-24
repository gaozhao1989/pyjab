pyjab
================================================================

本软件是使用 `Java Access Bridge`_ 进行 Java UI 程序的自动化实现的 Python 工具.

本软件 `pyjab` 可以让 Java UI 程序以自动化的方式执行（类似于 Selenium）。
该软件将会调用 `Java Access Bridge`_ API 从 Java UI 程序中获取信息。
该软件仅支持 Windows 操作系统。
该软件的源代码参考 `NVDA`_。

.. contents::
   :local:

安装
------------

您可以从 `PyPI`_ 找到 `pyjab` 的软件包，这意味着您可以使用如下简单的方式进行安装:

.. code-block:: console

   $ pip install pyjab

实际上有多种安装 Python 包的方法
（例如，`per user site-packages directory`_ 、`virtual environments`_ ），
这里不进行展开讨论，如果这让您感到疑惑，请先于此说明前阅读这些内容。

可选依赖包
~~~~~~~~~~~~~~~~~~~~~

`Access Bridge Explorer`_ 是一个可进行 Java UI 程序浏览的 Windows 应用程序，
该程序提供易于访问的方式甄别 Java UI 程序的内容，
并使用 Java Access Bridge 公开其可访问性功能，
例如： Android Studio 和 IntelliJ。

使用方式
-----

该软件需要 JRE、JDK 或 JAB 独立包。
推荐在使用前设置名为  ``JAVA_HOME`` 或 ``JAB_HOME`` 的环境变量。

下面是一个入门的简单示例：

.. code-block:: python

   from pyjab.jabdriver import JABDriver

   # 创建一个 JABDriver 的对象
   jabdriver = JABDriver("java app window title")

   # 使用 element name 找到一个 JABElement 对象
   login_btn = jabdriver.find_element_by_name("Login")

   # 点击一个 JABElement 对象
   login_btn.click()

   # 其他的一些例子
   jabdriver.find_element_by_xpath("//push button[@name=contains('OK')]")
   jabdriver.wait_until_element_exist(by=By.NAME, value="Dashboard")
   login_btn.get_screenshot_as_file("./screenshot.png")

联络
-------

`pyjab` 的最新版本可在 `PyPI`_ 和 `GitHub`_ 上获得。
如果发现该软件的问题，请不吝在 `GitHub`_ 上创建一个问题。 
如有疑问、建议等，也请随时给我发送电子邮件至 `gaozhao89@qq.com`_。

许可证
-------

该软件使用的许可证为 `GPLv2 license`_.

© 2021 Gary Gao.


.. External references:
.. _Java Access Bridge: https://docs.oracle.com/javase/accessbridge/2.0.2/toc.htm
.. _NVDA: https://github.com/nvaccess/nvda
.. _PyPI: https://pypi.org/
.. _GitHub: https://github.com/
.. _Access Bridge Explorer: https://github.com/google/access-bridge-explorer
.. _per user site-packages directory: https://www.python.org/dev/peps/pep-0370/
.. _virtual environments: http://docs.python-guide.org/en/latest/dev/virtualenvs/
.. _gaozhao89@qq.com: gaozhao89@qq.com
.. _GPLv2 license: https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html
