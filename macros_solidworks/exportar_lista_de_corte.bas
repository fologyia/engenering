' Mecanica Toolkit - exporta a lista de corte (soldagens) e o esqueleto da peca aberta para CSV.
'
' Le direto da arvore da peca: nao precisa de desenho nem de tabela.
' Uso (uma vez): com a peca aberta, Ferramentas > Macro > Nova..., de um nome e salve; no editor
' que abrir, apague tudo, cole este texto inteiro e tecle F5.
' Das proximas vezes: Ferramentas > Macro > Executar... e escolha a macro salva.
'
' Saem dois arquivos na pasta da peca:
' - <peca>_lista_de_corte.csv: envie na pagina "Lista de material" do Mecanica Toolkit;
' - <peca>_esqueleto.csv: cada corpo com a linha de centro (mm), a forma (barra, chapa ou bloco),
'   as medidas, a direcao da medida maior da secao (a alma), a direcao 1 do Simulation (a
'   aresta reta mais longa da secao) e o volume; nas chapas, o contorno da face maior e as
'   aberturas. Envie na pagina "Esforcos do modelo" junto com os CSV do
'   Simulation (pilares, vigas e contraventamentos, comprimentos de flambagem, perfis) e use em
'   "Cargas do esqueleto" (a carga do piso distribuida pelas vigas que apoiam cada chapa).
'
' Robustez: se algo der errado, a macro diz em que etapa parou e por que (arquivo aberto no Excel,
' pasta sem permissao...), fecha os arquivos e nao mexe na peca. Um corpo cuja geometria nao pode
' ser lida fica de fora e e listado no aviso final; os outros saem normalmente. Os numeros saem
' sempre com virgula decimal, qualquer que seja a configuracao regional do Windows.
Option Explicit

Const VERSAO_DA_MACRO As String = "v6"
Const DENSIDADE_ACO As Double = 7850#

Dim nomes() As String
Dim totalNomes As Long
Dim etapa As String
Dim arquivo As Integer
Dim arquivoEsqueleto As Integer
Dim problemas As String
Dim totalProblemas As Long

Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    On Error GoTo Falha
    ' Um arquivo que ficou aberto numa execucao interrompida trava a proxima: fecha tudo antes.
    Close
    arquivo = 0
    arquivoEsqueleto = 0
    problemas = ""
    totalProblemas = 0

    etapa = "abrir a peca"
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        MsgBox "Abra a peca (o arquivo da estrutura) antes de rodar a macro.", vbExclamation
        Exit Sub
    End If
    If swModel.GetType <> swDocPART Then
        MsgBox "A macro le a lista de corte de uma PECA. Abra o arquivo da peca, nao o desenho nem a montagem.", vbExclamation
        Exit Sub
    End If
    If swModel.GetPathName = "" Then
        MsgBox "Salve a peca antes: os CSV saem na mesma pasta dela.", vbExclamation
        Exit Sub
    End If

    etapa = "reconstruir a peca"
    swModel.ForceRebuild3 False

    ' 1) Atualiza a lista de corte e junta os itens (pastas da lista de corte).
    etapa = "ler a lista de corte"
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

    ' 2) Todas as propriedades que aparecem em algum item viram colunas.
    etapa = "ler as propriedades da lista de corte"
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

    ' 4) Cabecalho dos dois arquivos: peca, configuracao, data e versao da macro.
    Dim base As String, peca As String, configuracao As String, quando As String
    base = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, ".") - 1)
    peca = Mid(swModel.GetPathName, InStrRev(swModel.GetPathName, "\") + 1)
    configuracao = NomeDaConfiguracao(swModel)
    quando = Format(Now, "yyyy-mm-dd hh:nn")

    Dim caminho As String, caminhoEsqueleto As String, linha As String
    caminho = base & "_lista_de_corte.csv"
    caminhoEsqueleto = base & "_esqueleto.csv"
    If pastas.Count > 0 Then
        etapa = "gravar " & caminho
        arquivo = FreeFile
        Open caminho For Output As #arquivo
        Cabecalho arquivo, peca, configuracao, quando
        linha = "ITEM;QTD.;DESCRICAO;COMPRIMENTO;NOME NA LISTA DE CORTE;" & _
            "VOLUME POR PECA (cm3);MASSA DO ACO POR PECA (kg);CAIXA (mm)"
        For j = 0 To totalNomes - 1
            linha = linha & ";" & Campo(nomes(j))
        Next j
        Print #arquivo, linha
    End If
    etapa = "gravar " & caminhoEsqueleto
    arquivoEsqueleto = FreeFile
    Open caminhoEsqueleto For Output As #arquivoEsqueleto
    Cabecalho arquivoEsqueleto, peca, configuracao, quando
    Print #arquivoEsqueleto, "CORPO;ITEM DA LISTA;DESCRICAO;FORMA;X1 (mm);Y1 (mm);Z1 (mm);" & _
        "X2 (mm);Y2 (mm);Z2 (mm);COMPRIMENTO (mm);SECAO A (mm);SECAO B (mm);VOLUME (cm3);" & _
        "DIRECAO A X;DIRECAO A Y;DIRECAO A Z;CONTORNO (mm);ABERTURAS (mm);DIRECAO 1 X;DIRECAO 1 Y;DIRECAO 1 Z;DIRECAO 1 FOLGA (mm)"

    ' 5) Um item por linha na lista de corte; um corpo por linha no esqueleto.
    Dim vistos As Object
    Set vistos = CreateObject("Scripting.Dictionary")
    Dim valor As String, resolvido As String, comprimento As String, descricao As String
    Dim vCorpos As Variant, vMassa As Variant, swCorpo As SldWorks.Body2
    Dim volume As Double, corpos As Long, k As Long, caixa As String
    Dim g(11) As Double, forma As String
    Dim totalCorpos As Long, barras As Long, chapas As Long, blocos As Long
    For i = 1 To pastas.Count
        Set swSub = pastas(i)
        etapa = "ler o item " & swSub.Name & " da lista de corte"
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
        caixa = ""
        vCorpos = swPasta.GetBodies
        If IsArray(vCorpos) Then
            For k = 0 To UBound(vCorpos)
                Set swCorpo = vCorpos(k)
                vistos(swCorpo.Name) = True
                vMassa = Massa(swCorpo)
                If IsArray(vMassa) Then
                    volume = volume + vMassa(3)
                    corpos = corpos + 1
                End If
                If Geometria(swCorpo, vMassa, g, forma) Then
                    EscreverCorpo swCorpo, swSub.Name, descricao, forma, g, vMassa
                    totalCorpos = totalCorpos + 1
                    Contar forma, barras, chapas, blocos
                    ' Caixa de uma peca nas direcoes do proprio corpo (chapa inclinada tambem).
                    If caixa = "" Then
                        caixa = Num(g(6) * 1000#, "0.0") & " x " & _
                            Num(g(7) * 1000#, "0.0") & " x " & Num(g(8) * 1000#, "0.0")
                    End If
                Else
                    AnotarProblema swCorpo.Name
                End If
            Next k
            If caixa = "" Then
                ' Sem a geometria: a caixa nos eixos da peca.
                Set swCorpo = vCorpos(0)
                caixa = Num(Extensao(swCorpo, 1, 0, 0), "0.0") & " x " & _
                    Num(Extensao(swCorpo, 0, 1, 0), "0.0") & " x " & _
                    Num(Extensao(swCorpo, 0, 0, 1), "0.0")
            End If
        End If
        If corpos > 0 Then volume = volume / corpos
        linha = i & ";" & swPasta.GetBodyCount & ";" & Campo(descricao) & ";" & _
            Campo(comprimento) & ";" & Campo(swSub.Name) & ";" & _
            Campo(Num(volume * 1000000#, "0.0")) & ";" & Campo(Num(volume * DENSIDADE_ACO, "0.000")) & _
            ";" & Campo(caixa)
        For j = 0 To totalNomes - 1
            valor = ""
            resolvido = ""
            swProps.Get4 nomes(j), False, valor, resolvido
            linha = linha & ";" & Campo(resolvido)
        Next j
        Print #arquivo, linha
    Next i

    ' 6) Corpos fora de qualquer lista de corte (peca que nao e de soldagens, corpo solto).
    etapa = "ler os corpos fora da lista de corte"
    Dim swPart As SldWorks.PartDoc, vTodos As Variant, foraDaLista As Long
    Set swPart = swModel
    vTodos = swPart.GetBodies2(swSolidBody, False)
    If IsArray(vTodos) Then
        For k = 0 To UBound(vTodos)
            Set swCorpo = vTodos(k)
            If Not vistos.Exists(swCorpo.Name) Then
                vMassa = Massa(swCorpo)
                If Geometria(swCorpo, vMassa, g, forma) Then
                    EscreverCorpo swCorpo, "", "fora da lista de corte", forma, g, vMassa
                    totalCorpos = totalCorpos + 1
                    foraDaLista = foraDaLista + 1
                    Contar forma, barras, chapas, blocos
                Else
                    AnotarProblema swCorpo.Name
                End If
            End If
        Next k
    End If

    etapa = "fechar os arquivos"
    If arquivo <> 0 Then Close #arquivo
    arquivo = 0
    Close #arquivoEsqueleto
    arquivoEsqueleto = 0

    ' 7) Resumo.
    Dim texto As String
    If pastas.Count > 0 Then
        texto = pastas.Count & " itens da lista de corte exportados para:" & vbCrLf & caminho & vbCrLf & vbCrLf
    Else
        texto = "A peca nao tem lista de corte (nao e de soldagens): saiu so o esqueleto." & vbCrLf & vbCrLf
    End If
    texto = texto & totalCorpos & " corpos do esqueleto (" & barras & " barras, " & chapas & _
        " chapas, " & blocos & " blocos) exportados para:" & vbCrLf & caminhoEsqueleto
    If foraDaLista > 0 Then
        texto = texto & vbCrLf & vbCrLf & foraDaLista & " corpo(s) fora da lista de corte entraram no esqueleto."
    End If
    If totalProblemas > 0 Then
        texto = texto & vbCrLf & vbCrLf & "ATENCAO: " & totalProblemas & _
            " corpo(s) sem geometria legivel ficaram fora do esqueleto: " & problemas
        MsgBox texto, vbExclamation
    Else
        MsgBox texto, vbInformation
    End If
    Exit Sub

Falha:
    Dim numero As Long, descricaoDoErro As String
    numero = Err.Number
    descricaoDoErro = Err.Description
    On Error Resume Next
    Close
    Select Case numero
        Case 52, 53, 55, 70, 75, 76
            MsgBox "Nao consegui " & etapa & "." & vbCrLf & vbCrLf & _
                "O arquivo esta aberto em outro programa (feche-o no Excel) ou a pasta nao permite " & _
                "gravar (OneDrive sincronizando, pasta somente leitura). Feche, espere e rode a " & _
                "macro de novo." & vbCrLf & vbCrLf & "Erro " & numero & ": " & descricaoDoErro, vbExclamation
        Case Else
            MsgBox "A macro parou ao " & etapa & "." & vbCrLf & vbCrLf & "Erro " & numero & ": " & _
                descricaoDoErro & vbCrLf & vbCrLf & "A peca nao foi alterada. Se repetir, mande esta " & _
                "mensagem junto com o arquivo da peca.", vbExclamation
    End Select
End Sub

Function NomeDaConfiguracao(swModel As SldWorks.ModelDoc2) As String
    ' So informativo: se a API falhar, o arquivo sai sem o nome.
    On Error Resume Next
    NomeDaConfiguracao = ""
    NomeDaConfiguracao = swModel.ConfigurationManager.ActiveConfiguration.Name
End Function

Function Massa(swCorpo As SldWorks.Body2) As Variant
    ' Centro de massa (0 a 2) e volume (3, m3) do corpo; Empty se a API falhar.
    On Error Resume Next
    Massa = Empty
    Massa = swCorpo.GetMassProperties(DENSIDADE_ACO)
End Function

Sub Cabecalho(ByVal numeroDoArquivo As Integer, peca As String, configuracao As String, quando As String)
    Print #numeroDoArquivo, "MACRO;" & Campo("Mecanica Toolkit - exportar_lista_de_corte " & VERSAO_DA_MACRO)
    Print #numeroDoArquivo, "PECA;" & Campo(peca)
    Print #numeroDoArquivo, "CONFIGURACAO;" & Campo(configuracao)
    Print #numeroDoArquivo, "DATA;" & Campo(quando)
End Sub

Sub EscreverCorpo(swCorpo As SldWorks.Body2, item As String, descricao As String, forma As String, _
    g() As Double, vMassa As Variant)
    Dim volumeTexto As String, contorno As String, aberturas As String
    Dim d1(2) As Double, folga As Double, direcaoUm As String
    volumeTexto = ""
    If IsArray(vMassa) Then volumeTexto = Num(vMassa(3) * 1000000#, "0.0")
    contorno = ""
    aberturas = ""
    If forma = "CHAPA" Then
        If Not ContornoDaChapa(swCorpo, contorno, aberturas) Then
            contorno = ""
            aberturas = ""
        End If
    End If
    ' A direcao 1 do Simulation (so nas barras); sem ela, os quatro campos saem vazios.
    direcaoUm = ";;;"
    If forma = "BARRA" Then
        If DirecaoDaSecao(swCorpo, g, d1, folga) Then
            direcaoUm = Num(d1(0), "0.0000") & ";" & Num(d1(1), "0.0000") & ";" & _
                Num(d1(2), "0.0000") & ";" & Num(folga * 1000#, "0.0")
        End If
    End If
    Print #arquivoEsqueleto, Campo(swCorpo.Name) & ";" & Campo(item) & ";" & Campo(descricao) & ";" & _
        forma & ";" & _
        Num(g(0) * 1000#, "0.0") & ";" & Num(g(1) * 1000#, "0.0") & ";" & Num(g(2) * 1000#, "0.0") & ";" & _
        Num(g(3) * 1000#, "0.0") & ";" & Num(g(4) * 1000#, "0.0") & ";" & Num(g(5) * 1000#, "0.0") & ";" & _
        Num(g(6) * 1000#, "0.0") & ";" & Num(g(7) * 1000#, "0.0") & ";" & Num(g(8) * 1000#, "0.0") & ";" & _
        volumeTexto & ";" & _
        Num(g(9), "0.0000") & ";" & Num(g(10), "0.0000") & ";" & Num(g(11), "0.0000") & ";" & _
        Campo(contorno) & ";" & Campo(aberturas) & ";" & direcaoUm
End Sub

Function DirecaoDaSecao(swCorpo As SldWorks.Body2, g() As Double, d1() As Double, folga As Double) As Boolean
    ' A direcao 1 do Simulation: paralela a aresta reta mais longa da secao (ajuda do SOLIDWORKS,
    ' "Beam Directions"). Cada aresta reta da secao e a largura de uma face plana ao longo da
    ' barra (normal perpendicular ao eixo), medida pelos vertices da face na direcao eixo x
    ' normal. folga: quanto a face mais larga passa a mais larga das outras direcoes (m); perto
    ' de zero e empate (tubo quadrado, cantoneira de abas iguais) e o Simulation escolhe sozinho.
    ' O sentido da direcao 1 nao sai da geometria: o programa o tira dos resultados.
    Dim ux As Double, uy As Double, uz As Double, k As Long, j As Long, n As Long, lado As Long
    Dim vFaces As Variant, swFace As SldWorks.Face2, swSuperficie As SldWorks.Surface
    Dim vNormal As Variant, tx As Double, ty As Double, tz As Double, tamanho As Double
    Dim vArestas As Variant, swAresta As SldWorks.Edge, swVertice As SldWorks.Vertex
    Dim vPonto As Variant, s As Double, menor As Double, maior As Double, temPonto As Boolean
    Dim larguras() As Double, lx() As Double, ly() As Double, lz() As Double
    Dim melhor As Long, outra As Double
    On Error GoTo Falhou
    DirecaoDaSecao = False
    folga = 0#
    If g(6) <= 0# Then Exit Function
    ux = (g(3) - g(0)) / g(6)
    uy = (g(4) - g(1)) / g(6)
    uz = (g(5) - g(2)) / g(6)
    vFaces = swCorpo.GetFaces
    If Not IsArray(vFaces) Then Exit Function
    ReDim larguras(UBound(vFaces))
    ReDim lx(UBound(vFaces))
    ReDim ly(UBound(vFaces))
    ReDim lz(UBound(vFaces))
    n = 0
    For k = 0 To UBound(vFaces)
        Set swFace = vFaces(k)
        Set swSuperficie = swFace.GetSurface
        If Not swSuperficie Is Nothing Then
            If swSuperficie.IsPlane Then
                vNormal = swFace.Normal
                If IsArray(vNormal) Then
                    If Abs(vNormal(0) * ux + vNormal(1) * uy + vNormal(2) * uz) < 0.02 Then
                        tx = uy * vNormal(2) - uz * vNormal(1)
                        ty = uz * vNormal(0) - ux * vNormal(2)
                        tz = ux * vNormal(1) - uy * vNormal(0)
                        tamanho = Sqr(tx * tx + ty * ty + tz * tz)
                        If tamanho > 0.5 Then
                            tx = tx / tamanho
                            ty = ty / tamanho
                            tz = tz / tamanho
                            temPonto = False
                            vArestas = swFace.GetEdges
                            If IsArray(vArestas) Then
                                For j = 0 To UBound(vArestas)
                                    Set swAresta = vArestas(j)
                                    For lado = 0 To 1
                                        If lado = 0 Then
                                            Set swVertice = swAresta.GetStartVertex
                                        Else
                                            Set swVertice = swAresta.GetEndVertex
                                        End If
                                        If Not swVertice Is Nothing Then
                                            vPonto = swVertice.GetPoint
                                            s = vPonto(0) * tx + vPonto(1) * ty + vPonto(2) * tz
                                            If Not temPonto Then
                                                menor = s
                                                maior = s
                                                temPonto = True
                                            Else
                                                If s < menor Then menor = s
                                                If s > maior Then maior = s
                                            End If
                                        End If
                                    Next lado
                                Next j
                            End If
                            If temPonto Then
                                larguras(n) = maior - menor
                                lx(n) = tx
                                ly(n) = ty
                                lz(n) = tz
                                n = n + 1
                            End If
                        End If
                    End If
                End If
            End If
        End If
    Next k
    If n = 0 Then Exit Function
    melhor = 0
    For k = 1 To n - 1
        If larguras(k) > larguras(melhor) Then melhor = k
    Next k
    If larguras(melhor) <= 0# Then Exit Function
    outra = 0#
    For k = 0 To n - 1
        If Abs(lx(k) * lx(melhor) + ly(k) * ly(melhor) + lz(k) * lz(melhor)) < 0.9 Then
            If larguras(k) > outra Then outra = larguras(k)
        End If
    Next k
    d1(0) = lx(melhor)
    d1(1) = ly(melhor)
    d1(2) = lz(melhor)
    folga = larguras(melhor) - outra
    DirecaoDaSecao = True
    Exit Function
Falhou:
    DirecaoDaSecao = False
End Function

Function ContornoDaChapa(swCorpo As SldWorks.Body2, contorno As String, aberturas As String) As Boolean
    ' O contorno da face plana maior da chapa (o laco externo) e as aberturas (os lacos internos),
    ' em mm: "x y z | x y z | ...", aberturas separadas por "||".
    Dim vFaces As Variant, k As Long, swFace As SldWorks.Face2, area As Double, maior As Double
    Dim swMaior As SldWorks.Face2, swSuperficie As SldWorks.Surface
    Dim vLacos As Variant, swLaco As SldWorks.Loop2, texto As String
    On Error GoTo Falhou
    ContornoDaChapa = False
    contorno = ""
    aberturas = ""
    maior = 0
    vFaces = swCorpo.GetFaces
    If Not IsArray(vFaces) Then Exit Function
    For k = 0 To UBound(vFaces)
        Set swFace = vFaces(k)
        Set swSuperficie = swFace.GetSurface
        If Not swSuperficie Is Nothing Then
            If swSuperficie.IsPlane Then
                area = swFace.GetArea
                If area > maior Then
                    maior = area
                    Set swMaior = swFace
                End If
            End If
        End If
    Next k
    If swMaior Is Nothing Then Exit Function
    vLacos = swMaior.GetLoops
    If Not IsArray(vLacos) Then Exit Function
    For k = 0 To UBound(vLacos)
        Set swLaco = vLacos(k)
        texto = PontosDoLaco(swLaco)
        If texto <> "" Then
            If swLaco.IsOuter Then
                contorno = texto
            Else
                If aberturas <> "" Then aberturas = aberturas & " || "
                aberturas = aberturas & texto
            End If
        End If
    Next k
    ContornoDaChapa = (contorno <> "")
    Exit Function
Falhou:
    ContornoDaChapa = False
End Function

Function PontosDoLaco(swLaco As SldWorks.Loop2) As String
    ' Os pontos de um laco, na ordem das co-arestas; um furo redondo (um trecho so, fechado) sai
    ' com 12 pontos no circulo.
    Dim vCoArestas As Variant, k As Long, texto As String
    Dim swCo As SldWorks.CoEdge, vParams As Variant, swCurva As SldWorks.Curve, vCirculo As Variant
    Dim rx As Double, ry As Double, rz As Double, sx As Double, sy As Double, sz As Double
    Dim angulo As Double
    PontosDoLaco = ""
    vCoArestas = swLaco.GetCoEdges
    If Not IsArray(vCoArestas) Then Exit Function
    If UBound(vCoArestas) = 0 Then
        Set swCo = vCoArestas(0)
        Set swCurva = swCo.GetEdge.GetCurve
        vParams = swCo.GetCurveParams
        If Not swCurva Is Nothing And IsArray(vParams) Then
            If swCurva.IsCircle Then
                vCirculo = swCurva.CircleParams
                rx = vParams(0) - vCirculo(0)
                ry = vParams(1) - vCirculo(1)
                rz = vParams(2) - vCirculo(2)
                sx = vCirculo(4) * rz - vCirculo(5) * ry
                sy = vCirculo(5) * rx - vCirculo(3) * rz
                sz = vCirculo(3) * ry - vCirculo(4) * rx
                For k = 0 To 11
                    angulo = k * 3.14159265358979 / 6#
                    If texto <> "" Then texto = texto & " | "
                    texto = texto & Ponto(vCirculo(0) + rx * Cos(angulo) + sx * Sin(angulo), _
                        vCirculo(1) + ry * Cos(angulo) + sy * Sin(angulo), _
                        vCirculo(2) + rz * Cos(angulo) + sz * Sin(angulo))
                Next k
                PontosDoLaco = texto
                Exit Function
            End If
        End If
    End If
    For k = 0 To UBound(vCoArestas)
        Set swCo = vCoArestas(k)
        vParams = swCo.GetCurveParams
        If IsArray(vParams) Then
            If texto <> "" Then texto = texto & " | "
            texto = texto & Ponto(vParams(0), vParams(1), vParams(2))
        End If
    Next k
    PontosDoLaco = texto
End Function

Function Ponto(ByVal x As Double, ByVal y As Double, ByVal z As Double) As String
    Ponto = Num(x * 1000#, "0.0") & " " & Num(y * 1000#, "0.0") & " " & Num(z * 1000#, "0.0")
End Function

Sub Contar(forma As String, barras As Long, chapas As Long, blocos As Long)
    Select Case forma
        Case "BARRA": barras = barras + 1
        Case "CHAPA": chapas = chapas + 1
        Case Else: blocos = blocos + 1
    End Select
End Sub

Sub AnotarProblema(nomeDoCorpo As String)
    totalProblemas = totalProblemas + 1
    If totalProblemas <= 10 Then
        If problemas <> "" Then problemas = problemas & ", "
        problemas = problemas & nomeDoCorpo
    ElseIf totalProblemas = 11 Then
        problemas = problemas & "..."
    End If
End Sub

Function Geometria(swCorpo As SldWorks.Body2, vMassa As Variant, g() As Double, forma As String) As Boolean
    ' A linha de centro e as medidas do corpo, nas direcoes do proprio corpo (m):
    ' g(0..2) uma ponta, g(3..5) a outra, g(6) comprimento, g(7) e g(8) as medidas da secao
    ' (a maior e a menor), g(9..11) a direcao da medida maior (unitaria). As direcoes sao as principais da nuvem de pontos do corpo (vertices e
    ' centros das arestas circulares: um tubo redondo nao tem vertice); as medidas, os pontos
    ' extremos do corpo nessas direcoes; a linha de centro passa pelo centro de massa.
    Dim px() As Double, py() As Double, pz() As Double, n As Long, k As Long
    Dim vVertices As Variant, swVertice As SldWorks.Vertex, vPonto As Variant
    Dim vArestas As Variant, swAresta As SldWorks.Edge, swCurva As SldWorks.Curve, vCirculo As Variant
    On Error GoTo Falhou
    Geometria = False
    forma = ""
    n = 0
    ReDim px(31)
    ReDim py(31)
    ReDim pz(31)
    vVertices = swCorpo.GetVertices
    If IsArray(vVertices) Then
        For k = 0 To UBound(vVertices)
            Set swVertice = vVertices(k)
            vPonto = swVertice.GetPoint
            AcrescentarPonto px, py, pz, n, vPonto(0), vPonto(1), vPonto(2)
        Next k
    End If
    vArestas = swCorpo.GetEdges
    If IsArray(vArestas) Then
        For k = 0 To UBound(vArestas)
            Set swAresta = vArestas(k)
            Set swCurva = swAresta.GetCurve
            If Not swCurva Is Nothing Then
                If swCurva.IsCircle Then
                    vCirculo = swCurva.CircleParams
                    If IsArray(vCirculo) Then
                        AcrescentarPonto px, py, pz, n, vCirculo(0), vCirculo(1), vCirculo(2)
                    End If
                End If
            End If
        Next k
    End If
    If n < 2 Then Exit Function

    ' Centro: o de massa (fica na linha de centro de uma barra); sem ele, a media dos pontos.
    Dim cx As Double, cy As Double, cz As Double
    For k = 0 To n - 1
        cx = cx + px(k)
        cy = cy + py(k)
        cz = cz + pz(k)
    Next k
    cx = cx / n
    cy = cy / n
    cz = cz / n
    Dim a(2, 2) As Double, dx As Double, dy As Double, dz As Double
    For k = 0 To n - 1
        dx = px(k) - cx
        dy = py(k) - cy
        dz = pz(k) - cz
        a(0, 0) = a(0, 0) + dx * dx
        a(0, 1) = a(0, 1) + dx * dy
        a(0, 2) = a(0, 2) + dx * dz
        a(1, 1) = a(1, 1) + dy * dy
        a(1, 2) = a(1, 2) + dy * dz
        a(2, 2) = a(2, 2) + dz * dz
    Next k
    a(1, 0) = a(0, 1)
    a(2, 0) = a(0, 2)
    a(2, 1) = a(1, 2)
    If IsArray(vMassa) Then
        cx = vMassa(0)
        cy = vMassa(1)
        cz = vMassa(2)
    End If
    Dim v(2, 2) As Double
    Jacobi a, v

    ' Medidas nas tres direcoes principais; a maior e o eixo da barra.
    Dim tMenos(2) As Double, tMais(2) As Double, medida(2) As Double
    For k = 0 To 2
        tMais(k) = Extremo(swCorpo, v(0, k), v(1, k), v(2, k), cx, cy, cz)
        tMenos(k) = -Extremo(swCorpo, -v(0, k), -v(1, k), -v(2, k), cx, cy, cz)
        medida(k) = tMais(k) - tMenos(k)
    Next k
    Dim eixo As Long, segunda As Long, terceira As Long
    eixo = 0
    If medida(1) > medida(eixo) Then eixo = 1
    If medida(2) > medida(eixo) Then eixo = 2
    segunda = (eixo + 1) Mod 3
    terceira = (eixo + 2) Mod 3
    If medida(terceira) > medida(segunda) Then
        k = segunda
        segunda = terceira
        terceira = k
    End If
    If medida(eixo) <= 0 Then Exit Function
    g(0) = cx + tMenos(eixo) * v(0, eixo)
    g(1) = cy + tMenos(eixo) * v(1, eixo)
    g(2) = cz + tMenos(eixo) * v(2, eixo)
    g(3) = cx + tMais(eixo) * v(0, eixo)
    g(4) = cy + tMais(eixo) * v(1, eixo)
    g(5) = cz + tMais(eixo) * v(2, eixo)
    g(6) = medida(eixo)
    g(7) = medida(segunda)
    g(8) = medida(terceira)
    ' A direcao da medida maior da secao (a alma de um I ou de um U).
    g(9) = v(0, segunda)
    g(10) = v(1, segunda)
    g(11) = v(2, segunda)
    ' Chapa: muito fina para a largura (piso, gusset, chapa de base); barra: comprida para a secao.
    If g(8) <= 0.1 * g(7) And g(6) < 6# * g(7) Then
        forma = "CHAPA"
    ElseIf g(6) >= 2# * g(7) Then
        forma = "BARRA"
    ElseIf g(8) <= 0.25 * g(7) Then
        forma = "CHAPA"
    Else
        forma = "BLOCO"
    End If
    Geometria = True
    Exit Function
Falhou:
    Geometria = False
End Function

Sub AcrescentarPonto(px() As Double, py() As Double, pz() As Double, n As Long, _
    ByVal x As Double, ByVal y As Double, ByVal z As Double)
    If n > UBound(px) Then
        ReDim Preserve px(2 * n + 1)
        ReDim Preserve py(2 * n + 1)
        ReDim Preserve pz(2 * n + 1)
    End If
    px(n) = x
    py(n) = y
    pz(n) = z
    n = n + 1
End Sub

Sub Jacobi(a() As Double, v() As Double)
    ' Autovetores da matriz simetrica 3 x 3 (colunas de v), pelo metodo de Jacobi.
    Dim i As Long, j As Long, k As Long, p As Long, q As Long, varredura As Long
    Dim fora As Double, escala As Double, theta As Double, t As Double, c As Double, s As Double
    Dim x As Double, y As Double
    For i = 0 To 2
        For j = 0 To 2
            v(i, j) = 0#
        Next j
        v(i, i) = 1#
    Next i
    For varredura = 1 To 50
        fora = a(0, 1) * a(0, 1) + a(0, 2) * a(0, 2) + a(1, 2) * a(1, 2)
        escala = a(0, 0) * a(0, 0) + a(1, 1) * a(1, 1) + a(2, 2) * a(2, 2) + fora
        If fora <= 1E-24 * escala Then Exit Sub
        For p = 0 To 1
            For q = p + 1 To 2
                If Abs(a(p, q)) > 1E-15 * (Abs(a(p, p)) + Abs(a(q, q))) Then
                    theta = (a(q, q) - a(p, p)) / (2# * a(p, q))
                    t = 1# / (Abs(theta) + Sqr(theta * theta + 1#))
                    If theta < 0 Then t = -t
                    c = 1# / Sqr(t * t + 1#)
                    s = t * c
                    For k = 0 To 2
                        x = a(k, p)
                        y = a(k, q)
                        a(k, p) = c * x - s * y
                        a(k, q) = s * x + c * y
                    Next k
                    For k = 0 To 2
                        x = a(p, k)
                        y = a(q, k)
                        a(p, k) = c * x - s * y
                        a(q, k) = s * x + c * y
                    Next k
                    For k = 0 To 2
                        x = v(k, p)
                        y = v(k, q)
                        v(k, p) = c * x - s * y
                        v(k, q) = s * x + c * y
                    Next k
                End If
            Next q
        Next p
    Next varredura
End Sub

Function Extremo(swCorpo As SldWorks.Body2, ByVal ex As Double, ByVal ey As Double, ByVal ez As Double, _
    ByVal cx As Double, ByVal cy As Double, ByVal cz As Double) As Double
    ' Quanto o corpo vai alem do centro na direcao (ex, ey, ez), em m.
    Dim x As Double, y As Double, z As Double
    swCorpo.GetExtremePoint ex, ey, ez, x, y, z
    Extremo = (x - cx) * ex + (y - cy) * ey + (z - cz) * ez
End Function

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

Function Num(ByVal valor As Double, formato As String) As String
    ' Virgula decimal sempre (o formato "0.0" nao tem separador de milhar em nenhum Windows).
    Num = Replace(Format(valor, formato), ".", ",")
End Function

Function Campo(texto As String) As String
    Dim t As String
    t = Replace(Replace(texto, vbCr, " "), vbLf, " ")
    Campo = """" & Replace(t, """", """""") & """"
End Function
