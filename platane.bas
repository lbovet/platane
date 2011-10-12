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

    ' The construction of the URL depends on your structure. Adapt accordingly.'
    url = "http://platane/branches/BRANCH/units/UNIT/teams/TEAM/people/USER/tasks/outlook/"
    Set NameSpace = Application.GetNamespace("MAPI")
    LogonName = fOSUserName()
    UserName = NameSpace.CurrentUser
    UnitPosition = InStr(UserName, ", ")
    UnitPosition = UnitPosition + 2
    SubUnit = Mid(UserName, UnitPosition)
    url = Replace(url, "USER", LogonName)
    If Len(SubUnit) = 5 Then
        url = Replace(url, "TEAM", SubUnit)
    Else
        url = Replace(url, "TEAM", "default")
    End If
    url = Replace(url, "UNIT", Left(SubUnit, 4))
    url = Replace(url, "BRANCH", Left(SubUnit, 3))

    result = Send(url, "method=DELETE")
    If Not result = "OK" Then
        MsgBox (result)
        Exit Sub
    End If
    
    Dim intCounter As Integer

    Set calFolder = NameSpace.GetDefaultFolder(9)
    
    Message = " events sent to Platane:" + Chr(10)
    
    today = Date - 1
    todayString = FormatDateTime(today, vbShortDate) & " " & FormatDateTime(today, vbShortTime)
    after = Date + 120
    afterString = FormatDateTime(after, vbShortDate) & " " & FormatDateTime(after, vbShortTime)
    
    For Each Item In calFolder.Items.Restrict("[BusyStatus] = 3 and [End] > '" & todayString & "' and [Start] < '" & afterString & "'")
        If Item.RecurrenceState = olApptNotRecurring And Item.Duration > 24 * 60 Then
            intCounter = intCounter + 1
            ItemName = Item.Subject
            ItemName = Replace(ItemName, "[", "(")
            ItemName = Replace(ItemName, "]", ")")
            task = "absence [" & ItemName & " " & intCounter & "]"
            Message = Message & Chr(13) & Chr(10) & Item
            
            StartDate = FormatDateTime(Item.Start, vbShortDate)
            EndDate = FormatDateTime(Item.End - 1, vbShortDate)
            
            Set webClient = CreateObject("WinHttp.WinHttpRequest.5.1")
            result = Send(url & task & "/", "name=" & task & "&load=100&from=" & StartDate & "&to=" & EndDate & "&absence=true")
            If Not result = "OK" Then
                MsgBox (result)
                Exit Sub
            End If
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

Function Send(url, data) As String
    Set webClient = CreateObject("WinHttp.WinHttpRequest.5.1")
    webClient.SetAutoLogonPolicy (0)
    webClient.Option(6) = False 'Prevent redirects
    webClient.Open "POST", url, False
    webClient.Send (data)
    webClient.WaitForResponse
    If webClient.Status = "200" Or webClient.Status = "302" Then
        Send = "OK"
    Else
        Send = "Problem while sending to Platane: Error " & webClient.Status
    End If
End Function


