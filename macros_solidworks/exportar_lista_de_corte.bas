' Mecanica Toolkit - exporta a lista de corte (soldagens) da peca aberta para CSV.
'
' Le direto da arvore da peca: nao precisa de desenho nem de tabela.
' Uso (uma vez): com a peca aberta, Ferramentas > Macro > Nova..., de um nome e salve; no editor
' que abrir, apague tudo, cole este texto inteiro e tecle F5.
' Das proximas vezes: Ferramentas > Macro > Executar... e escolha a macro salva.
'
' O CSV sai na pasta da peca, com o nome <peca>_lista_de_corte.csv. Envie-o na pagina
' "Lista de material" do Mecanica Toolkit.
Option Explicit

Dim nomes() As String
Dim totalNomes As Long

Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        MsgBox "Abra a peca (o arquivo da estrutura) antes de rodar a macro."
        Exit Sub
    End If
    If swModel.GetType <> swDocPART Then
        MsgBox "A macro le a lista de corte de uma PECA. Abra o arquivo da peca, nao o desenho nem a montagem."
        Exit Sub
    End If
    If swModel.GetPathName = "" Then
        MsgBox "Salve a peca antes: o CSV sai na mesma pasta dela."
        Exit Sub
    End If
    swModel.ForceRebuild3 False

    ' 1) Atualiza a lista de corte e junta os itens (pastas da lista de corte).
    Dim pastas As New Collection
    Dim swFeat As SldWorks.Feature
    Dim swSub As SldWorks.Feature
    Dim swPasta As SldWorks.BodyFolder
    Set swFeat = swModel.FirstFeature
    Do While Not swFeat Is Nothing
        If swFeat.GetTypeName2 = "SolidBodyFolder" Then
            Set swPasta = swFeat.GetSpecificFeature2
            swPasta.UpdateCutList
            Set swSub = swFeat.GetFirstSubFeature
            Do While Not swSub Is Nothing
                If swSub.GetTypeName2 = "CutListFolder" Then Juntar pastas, swSub
                Set swSub = swSub.GetNextSubFeature
            Loop
        ElseIf swFeat.GetTypeName2 = "CutListFolder" Then
            Juntar pastas, swFeat
        End If
        Set swFeat = swFeat.GetNextFeature
    Loop
    If pastas.Count = 0 Then
        MsgBox "Nenhum item de lista de corte encontrado. A peca precisa ser de soldagens (membros estruturais)."
        Exit Sub
    End If

    ' 2) Todas as propriedades que aparecem em algum item viram colunas.
    Dim i As Long, j As Long
    Dim swProps As SldWorks.CustomPropertyManager
    Dim vNomes As Variant
    totalNomes = 0
    ReDim nomes(0)
    For i = 1 To pastas.Count
        Set swSub = pastas(i)
        Set swProps = swSub.CustomPropertyManager
        vNomes = swProps.GetNames
        If IsArray(vNomes) Then
            For j = 0 To UBound(vNomes)
                AcrescentarNome CStr(vNomes(j))
            Next j
        End If
    Next i

    ' 3) Unidade de comprimento do documento, escrita junto de cada comprimento.
    Dim unidade As String
    Select Case swModel.GetUserPreferenceIntegerValue(swUnitsLinear)
        Case swMM: unidade = "mm"
        Case swCM: unidade = "cm"
        Case swMETER: unidade = "m"
        Case swINCHES: unidade = "in"
        Case swFEET: unidade = "ft"
        Case Else: unidade = ""
    End Select

    ' 4) Grava o CSV (separador ponto e virgula).
    Dim caminho As String
    caminho = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, ".") - 1) & "_lista_de_corte.csv"
    Dim arquivo As Integer
    arquivo = FreeFile
    Open caminho For Output As #arquivo
    Dim linha As String
    linha = "ITEM;QTD.;DESCRICAO;COMPRIMENTO;NOME NA LISTA DE CORTE;" & _
        "VOLUME POR PECA (cm3);MASSA DO ACO POR PECA (kg);CAIXA (mm)"
    For j = 0 To totalNomes - 1
        linha = linha & ";" & Campo(nomes(j))
    Next j
    Print #arquivo, linha

    Dim valor As String, resolvido As String, comprimento As String, descricao As String
    Dim vCorpos As Variant, vMassa As Variant, swCorpo As SldWorks.Body2
    Dim volume As Double, corpos As Long, k As Long, caixa As String
    For i = 1 To pastas.Count
        Set swSub = pastas(i)
        Set swPasta = swSub.GetSpecificFeature2
        Set swProps = swSub.CustomPropertyManager
        comprimento = ""
        descricao = SemSufixo(swSub.Name)
        For j = 0 To totalNomes - 1
            valor = ""
            resolvido = ""
            If UCase(nomes(j)) = "LENGTH" Or UCase(nomes(j)) = "COMPRIMENTO" Then
                swProps.Get4 nomes(j), False, valor, resolvido
                If resolvido <> "" Then comprimento = resolvido
            ElseIf UCase(nomes(j)) Like "DESCRI*" And NomeGenerico(descricao) Then
                ' Item com nome automatico ("Item da lista de corte1"): vale a descricao do perfil.
                swProps.Get4 nomes(j), False, valor, resolvido
                If resolvido <> "" Then descricao = resolvido
            End If
        Next j
        If comprimento <> "" And unidade <> "" And Not (comprimento Like "*[A-Za-z]*") Then
            comprimento = comprimento & " " & unidade
        End If
        ' Volume medio de uma peca, pela geometria (m3); a massa e a do aco, 7850 kg/m3.
        volume = 0
        corpos = 0
        vCorpos = swPasta.GetBodies
        If IsArray(vCorpos) Then
            For k = 0 To UBound(vCorpos)
                Set swCorpo = vCorpos(k)
                vMassa = swCorpo.GetMassProperties(7850#)
                If IsArray(vMassa) Then
                    volume = volume + vMassa(3)
                    corpos = corpos + 1
                End If
            Next k
        End If
        If corpos > 0 Then volume = volume / corpos
        ' Caixa justa de uma peca nos eixos da peca (mm): pelas chapas, comprimento x largura x espessura.
        caixa = ""
        If IsArray(vCorpos) Then
            Set swCorpo = vCorpos(0)
            caixa = Format(Extensao(swCorpo, 1, 0, 0), "0.0") & " x " & _
                Format(Extensao(swCorpo, 0, 1, 0), "0.0") & " x " & _
                Format(Extensao(swCorpo, 0, 0, 1), "0.0")
        End If
        linha = i & ";" & swPasta.GetBodyCount & ";" & Campo(descricao) & ";" & _
            Campo(comprimento) & ";" & Campo(swSub.Name) & ";" & _
            Campo(Format(volume * 1000000#, "0.0")) & ";" & Campo(Format(volume * 7850#, "0.000")) & _
            ";" & Campo(caixa)
        For j = 0 To totalNomes - 1
            valor = ""
            resolvido = ""
            swProps.Get4 nomes(j), False, valor, resolvido
            linha = linha & ";" & Campo(resolvido)
        Next j
        Print #arquivo, linha
    Next i
    Close #arquivo
    MsgBox pastas.Count & " itens da lista de corte exportados para:" & vbCrLf & caminho
End Sub

Sub Juntar(pastas As Collection, swFeat As SldWorks.Feature)
    Dim k As Long
    For k = 1 To pastas.Count
        If pastas(k).Name = swFeat.Name Then Exit Sub
    Next k
    pastas.Add swFeat
End Sub

Sub AcrescentarNome(nome As String)
    Dim k As Long
    For k = 0 To totalNomes - 1
        If UCase(nomes(k)) = UCase(nome) Then Exit Sub
    Next k
    ReDim Preserve nomes(0 To totalNomes)
    nomes(totalNomes) = nome
    totalNomes = totalNomes + 1
End Sub

Function SemSufixo(nome As String) As String
    If InStr(nome, "<") > 0 Then
        SemSufixo = Trim(Left(nome, InStr(nome, "<") - 1))
    Else
        SemSufixo = Trim(nome)
    End If
End Function

Function Extensao(swCorpo As SldWorks.Body2, ByVal dx As Double, ByVal dy As Double, ByVal dz As Double) As Double
    ' Tamanho do corpo na direcao (dx, dy, dz), em mm: ponto extremo de um lado mais o do outro.
    Dim x1 As Double, y1 As Double, z1 As Double, x2 As Double, y2 As Double, z2 As Double
    swCorpo.GetExtremePoint dx, dy, dz, x1, y1, z1
    swCorpo.GetExtremePoint -dx, -dy, -dz, x2, y2, z2
    Extensao = Abs((x1 - x2) * dx + (y1 - y2) * dy + (z1 - z2) * dz) * 1000#
End Function

Function NomeGenerico(nome As String) As Boolean
    NomeGenerico = (LCase(nome) Like "item da lista de corte*") Or (LCase(nome) Like "cut-list-item*")
End Function

Function Campo(texto As String) As String
    Dim t As String
    t = Replace(Replace(texto, vbCr, " "), vbLf, " ")
    Campo = """" & Replace(t, """", """""") & """"
End Function
