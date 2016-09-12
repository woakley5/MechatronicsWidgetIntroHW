ArduinoPath = "C:\Users\WillOakley\Documents\Mechatronics\Programming Intro\FirstProject\hardware.json"

Dim ID
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject") 

'Kill previous node tasks
WshShell.run "taskkill /f /im cmd.exe /T", 0, True
WshShell.run "taskkill /f /im node.exe /T", 0, True

'Get hardware.json ready for reading/writing
Set objFile = CreateObject("Scripting.FileSystemObject").OpenTextFile(ArduinoPath,1)
        'Read the entire file into memory.
    strFileText = objFile.ReadAll
        'Close the file.
    objFile.Close
        'Split the file at the new line character. *Use the Line Feed character (Char(10))
    arrFileText = Split(strFileText,chr(10))
        'Open the file for writing.
    Set objFile = CreateObject("Scripting.FileSystemObject").OpenTextFile(ArduinoPath,2,true)

'Gets the arduino's serial id
strComputer = "." 
Set objWMIService = GetObject("winmgmts:" _ 
    & "{impersonationLevel=impersonate}!\\" & strComputer & "\root\cimv2")
    'Gets all USB devices
Set colItems = objWMIService.ExecQuery("Select * from Win32_SerialPort") 
'Gets the Serial ID of the Device (Obviously only works for our case if its an Arduino)
For Each objItem in colItems
  ID = Split(objItem.PNPDeviceID, "\")(2)
Next

'Write to hardware.json, replacing only the line containing the serial port with the correct serial port
For Each strLine in arrFileText
    If InStr(strLine,"serialNumber") > 0 Then
        strLine = Replace(strLine,strLine,"	    "&chr(34)&"serialNumber"&chr(34)&": " & chr(34) & CStr(ID) & chr(34))
        objFile.Write(strLine & chr(10))
    Else If Not(strLine = "" Or strLine = CStr(vbCrLf) Or strLine = CStr(chr(10))) Then
        objFile.Write(strLine & chr(10))
    End If 
    End If
Next