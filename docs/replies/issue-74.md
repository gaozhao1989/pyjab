Sorry for the silence, and thanks for the detailed report.

What you are describing -- the script freezing when a second window opens --
matches a known weak spot: after the first window is found, pyjab stops
driving the Windows message pump, so newly opened top-level windows and modal
dialogs may never be seen. I am fixing this in 1.3.0.

A few questions so I can confirm that is what you are hitting:

1. Does it freeze forever, or eventually raise a timeout?
2. Is the second window a **modal** dialog (does the first window stop
   responding until you close it)?
3. Does `simulate=True` anywhere in the script make it worse? That parameter
   forces the window to the foreground and can deadlock with a modal dialog.
4. Which JDK version is the target application running on?

**Workaround to try in the meantime:** instead of constructing a second
`JABDriver("Configuración de Archivos Temporales")`, reuse the first driver and
search for the dialog's contents through it, or poll
`driver.wait_until_element_exist(By.NAME, "Aceptar")`.

If you can attach a minimal script plus the JDK version, that would help a lot.
