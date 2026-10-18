' ==============================================================================
' WhisperDnD - Launcher Silencioso (Segundo Plano)
' Permite iniciar el servidor sin abrir ninguna ventana de consola ni pestaña de Python
' ==============================================================================
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

' Si existe pythonw en el entorno virtual, ejecutar directamente en modo totalmente silencioso
If fso.FileExists(scriptDir & "\.venv\Scripts\pythonw.exe") Then
    WshShell.Run Chr(34) & scriptDir & "\.venv\Scripts\pythonw.exe" & Chr(34) & " main.py", 0, False
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    WshShell.Run Chr(34) & scriptDir & "\.venv\Scripts\python.exe" & Chr(34) & " main.py", 0, False
Else
    WshShell.Run "pythonw main.py", 0, False
End If
