Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(scriptDir)
pythonw = "C:\Users\endy0\AppData\Local\Programs\Python\Python311\pythonw.exe"
launcher = fso.BuildPath(scriptDir, "run_private_drive_app.py")

shell.CurrentDirectory = projectRoot
shell.Run """" & pythonw & """ """ & launcher & """", 0, False
