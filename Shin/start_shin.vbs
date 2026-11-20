Set objShell = CreateObject("WScript.Shell")
strPath = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
objShell.CurrentDirectory = strPath

Set objFSO = CreateObject("Scripting.FileSystemObject")
pythonExe = strPath & ".venv\Scripts\pythonw.exe"

If Not objFSO.FileExists(pythonExe) Then
    If objFSO.FileExists(strPath & "..\.venv\Scripts\pythonw.exe") Then
        pythonExe = strPath & "..\.venv\Scripts\pythonw.exe"
    Else
        ' Fallback for non-venv installs: try to find pythonw in PATH
        pythonExe = objShell.Exec("where pythonw.exe").StdOut.ReadLine()
        If objShell.Exec("where pythonw.exe").ExitCode <> 0 Then
            pythonExe = "pythonw.exe" ' Last resort
        End If
    End If
End If

scriptPath = strPath & "assistant.py"

' Run the script silently (0 = hide window, False = don't wait for it to finish)
objShell.Run """" & pythonExe & """ """ & scriptPath & """", 0, False
