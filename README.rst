pyjab
================================================================

Python implementation for Java application UI automation with `Java Access Bridge`_.

The `pyjab` package enables run UI automation(selenium like) through with 
Java UI application.
Package will invoke `Java Access Bridge`_ API to get information form 
Java application.
And this package is only support for Windows(current for x86 version).
Sources code referenced from `NVDA`_.

.. contents::
   :local:

Installation
------------

The `pyjab` package is available on `PyPI`_ which means installation should
be as simple as:

.. code-block:: console

   $ pip install pyjab

There's actually a multitude of ways to install Python packages (e.g. the `per
user site-packages directory`_, `virtual environments`_ or just installing
system wide) and I have no intention of getting into that discussion here, so
if this intimidates you then read up on your options before returning to these
instructions.

Optional dependencies
~~~~~~~~~~~~~~~~~~~~~

`Access Bridge Explorer`_ is a Windows application that allows exploring, 
as well as interacting with, the Accessibility tree of any Java applications 
that uses the Java Access Bridge to expose their accessibility features, 
for example Android Studio and IntelliJ.

Usage
-----

JRE, JDK or JAB standalone package is required.
Need setup environment variable ``JAVA_HOME`` or ``JAB_HOME`` before usage. 

Here's an example of how easy it is to get started:

.. code-block:: python

   import pyjab

   # Create a JABDriver object.
   jabdriver = JABDriver("java app window title")

   # Find a JABElement by element name
   login_btn = jabdriver.find_element_by_name("Login")

   # Click a JABElement
   login_btn.click()

   # Some other examples.
   jabdriver.find_element_by_xpath("//push button[@name=contains('OK')]")
   jabdriver.wait_until_element_exist(by=By.NAME, value="Dashboard")
   login_btn.get_screenshot_as_file("./screenshot.png")

Contact
-------

The latest version of `pyjab` is available on `PyPI`_ and `GitHub`_. 
For bug reports please create an issue on `GitHub`_. If you have questions, 
suggestions, etc. feel free to send me an e-mail at `gaozhao89@qq.com`_.

License
-------

This software is licensed under the `GPLv2 license`_.

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
