Attribute VB_Name = "Platane"
'  Copyright 2011 Laurent Bovet <laurent.bovet@windmaster.ch>
'
'  This file is part of Platane.
'
'  Platane is free software: you can redistribute it and/or modify
'  it under the terms of the GNU Lesser General Public License as
'  published bythe Free Software Foundation, either version 3 of the
'  License, or (at your option) any later version.
'
'  Platane is distributed in the hope that it will be useful,
'  but WITHOUT ANY WARRANTY; without even the implied warranty of
'  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
'  GNU Lesser General Public License for more details.
'
'  You should have received a copy of the GNU Lesser General Public
'  License along with Platane.
'  If not, see <http://www.gnu.org/licenses/>.

Private Declare Function apiGetUserName Lib "advapi32.dll" Alias _
    "GetUserNameA" (ByVal lpBuffer As String, nSize As Long) As Long

Sub PlataneSync()

    Prefix = "http://maven:7780/units/"
    Middle = "/people/"
    Suffix = "/tasks/outlook/"
    
    Set NameSpace = Application.GetNamespace("MAPI")
    LogonName = fOSUserName()
    UserName = NameSpace.CurrentUser
    UnitPosition = InStr(UserName, ", ")
    UnitPosition = UnitPosition + 2
    Unit = Mid(UserName, UnitPosition)
    
    url = Prefix & Unit & Middle & LogonName & Suffix
    
    Set webClient = CreateObject("WinHttp.WinHttpRequest.5.1")
    webClient.Option(6) = False 'Prevent redirects
    webClient.Open "POST", url, False
    webClient.Send ("method=DELETE")
    
    Dim intCounter As Integer

    Set calFolder = NameSpace.GetDefaultFolder(9)
    
    today = Date - 1
    dateString = FormatDateTime(today, vbShortDate) & " " & FormatDateTime(today, vbShortTime)
    Message = " events sent to Platane:" + Chr(10)
    
    For Each Item In calFolder.Items.Restrict("[BusyStatus] = 3 and [End] > '" & dateString & "'")
        If Item.RecurrenceState = olApptNotRecurring And Item.Duration > 24 * 60 Then
            intCounter = intCounter + 1
            task = "absence [" & Item & " " & intCounter & "]"
            Message = Message & Chr(13) & Chr(10) & Item
            
            StartDate = FormatDateTime(Item.Start, vbShortDate)
            EndDate = FormatDateTime(Item.End - 1, vbShortDate)
            
            Set webClient = CreateObject("WinHttp.WinHttpRequest.5.1")
            webClient.Option(6) = False 'Prevent redirects
            webClient.Open "POST", url & task & "/", False
            PostData = "name=" & task & "&load=100&from=" & StartDate & "&to=" & EndDate & "&absence=true"
            webClient.Send (PostData)
        End If
    Next

    ' Display the results.
    MsgBox intCounter & Message
    
End Sub

Function fOSUserName() As String
' This code was originally written by Dev Ashish.
' It is not to be altered or distributed,
' except as part of an application.
' You are free to use it in any application,
' provided the copyright notice is left unchanged.
'
' Code Courtesy of
' Dev Ashish
'
' Returns the network login name
Dim lngLen As Long, lngX As Long
Dim strUserName As String
    strUserName = String$(254, 0)
    lngLen = 255
    lngX = apiGetUserName(strUserName, lngLen)
    If (lngX > 0) Then
        fOSUserName = Left$(strUserName, lngLen - 1)
    Else
        fOSUserName = vbNullString
    End If
End Function



