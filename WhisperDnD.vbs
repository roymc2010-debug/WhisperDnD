Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

batPath = strPath & "\iniciar_whisper_dnd.bat"
WshShell.CurrentDirectory = strPath
WshShell.Run """" & batPath & """", 0, False
