Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = folder & "\venv\Scripts\pythonw.exe"
If fso.FileExists(pythonw) Then
  shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & folder & "\NEGROSKY_CONTROL.pyw" & Chr(34), 0, False
Else
  MsgBox "Ejecute INSTALAR_WINDOWS.bat una sola vez antes de abrir el control.", 48, "NEGROSKY"
End If
