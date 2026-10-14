' Mecanica Toolkit - exporta os resultados de cada caso do gerenciador de casos de carga do
' SOLIDWORKS Simulation para CSV: o que a Vista de resultados mostra, sem passar pelo relatorio.
'
' Uso (uma vez): com a peca aberta e a aba do estudo do gerenciador selecionada, Ferramentas >
' Macro > Nova..., de um nome e salve; no editor que abrir, apague tudo, cole este texto inteiro e
' tecle F5. Das proximas vezes: Ferramentas > Macro > Executar... e escolha a macro salva.
' Antes de rodar, Executar no gerenciador: a macro so le os resultados ja calculados (nao roda o
' estudo e nao muda nada nele). Nao precisa marcar referencia nenhuma no editor: o Simulation e
' chamado pelo nome.
'
' Saem, na pasta da peca, para cada caso primario (PP, SC, W0...):
' - <estudo>-<caso>-forcas.csv: os esforcos de cada viga, elemento a elemento, no formato do
'   "Listar forcas da viga";
' - <estudo>-<caso>-reacoes.csv: a soma das reacoes do modelo, no formato do "Listar forcas
'   resultantes";
' e o quadro <estudo>-gerenciador-resultados.csv: cada sensor (as colunas da Vista de resultados)
' em cada caso primario e em cada combinacao.
' Envie os de forcas e de reacoes na pagina "Esforcos do modelo" do Mecanica Toolkit: o caso de
' cada arquivo vem do cabecalho ("Caso de carga: SC"). As combinacoes o programa faz pela NBR 8800.
'
' Robustez: se algo der errado, a macro diz em que etapa parou e por que (arquivo aberto no Excel,
' pasta sem permissao...) e fecha os arquivos. Uma viga ou um caso sem resultados fica de fora e e
' listado no aviso final; os outros saem normalmente. Os numeros saem com virgula decimal,
' qualquer que seja a configuracao regional do Windows.
Option Explicit

Const VERSAO_DA_MACRO As String = "v2"
Const PECA As Long = 1          ' swDocPART
Const CORPO_SOLIDO As Long = 0  ' swSolidBody
Const UNIDADES_SI As Long = 0   ' swsUnitSI: N e N.m
Const FORCA_EM_N As Long = 0    ' swsForceUnitNOrNm

Dim etapa As String
Dim arquivo As Integer
Dim problemas As String
Dim totalProblemas As Long
Dim ultimaFalha As String

Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swPeca As SldWorks.PartDoc
    Dim suplementoDoSimulation As Object
    Dim gerenteDeEstudos As Object
    Dim estudo As Object
    Dim gerenciador As Object
    Dim resultados As Object
    Dim corpos As Object
    Dim listaDeCorpos As Variant
    Dim corpo As Variant
    Dim casos As Variant
    Dim combinacoes As Variant
    Dim sensores As Variant
    Dim nomesDasVigas() As String
    Dim corposDasVigas() As Object
    Dim vigasDoEstudo() As Object
    Dim totalDeVigas As Long
    Dim valores(5) As Variant
    Dim soma As Variant
    Dim i As Long, j As Long, k As Long, e As Long, n As Long, base As Long
    Dim erro As Long
    Dim caso As String, pasta As String, nomeDoEstudo As String, quando As String
    Dim caminho As String, linha1 As String, linha2 As String
    Dim casosExportados As Long, vigasExportadas As Long
    Dim motivo As String, pelosCorpos As Boolean, ehViga() As Boolean
    Dim naoVigas As Long, jaClassificou As Boolean

    On Error GoTo Falha
    ' Um arquivo que ficou aberto numa execucao interrompida trava a proxima: fecha tudo antes.
    Close
    arquivo = 0
    problemas = ""
    totalProblemas = 0
    ultimaFalha = ""

    etapa = "abrir a peca"
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        MsgBox "Abra a peca com o estudo do gerenciador de casos de carga antes de rodar a macro.", vbExclamation
        Exit Sub
    End If
    If swModel.GetType <> PECA Then
        MsgBox "A macro le o estudo de uma PECA. Abra o arquivo da peca, nao o desenho nem a montagem.", vbExclamation
        Exit Sub
    End If
    If swModel.GetPathName = "" Then
        MsgBox "Salve a peca antes: os CSV saem na mesma pasta dela.", vbExclamation
        Exit Sub
    End If
    Set swPeca = swModel
    pasta = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, "\"))
    quando = Format(Now, "hh:nn") & "; " & Format(Now, "dd/mm/yyyy")

    etapa = "ligar ao SOLIDWORKS Simulation"
    Set suplementoDoSimulation = Suplemento(swApp)
    If suplementoDoSimulation Is Nothing Then
        MsgBox "Ligue o suplemento SOLIDWORKS Simulation (Ferramentas > Suplementos) e rode de novo.", vbExclamation
        Exit Sub
    End If
    Set gerenteDeEstudos = suplementoDoSimulation.CosmosWorks.ActiveDoc.StudyManager
    Set estudo = gerenteDeEstudos.GetStudy(gerenteDeEstudos.ActiveStudy)
    If estudo Is Nothing Then
        MsgBox "Selecione a aba do estudo do gerenciador de casos de carga e rode de novo.", vbExclamation
        Exit Sub
    End If
    nomeDoEstudo = estudo.Name

    etapa = "abrir o gerenciador de casos de carga do estudo " & nomeDoEstudo
    Set gerenciador = estudo.LoadCaseManager
    If gerenciador Is Nothing Then
        MsgBox "O estudo " & nomeDoEstudo & " nao tem gerenciador de casos de carga.", vbExclamation
        Exit Sub
    End If
    Tentar gerenciador, "abrir"
    casos = gerenciador.GetAllPrimaryLoadCaseNames()
    If Not TemItens(casos) Then
        MsgBox "O estudo " & nomeDoEstudo & " nao tem casos primarios no gerenciador de casos de carga.", vbExclamation
        Exit Sub
    End If
    combinacoes = NomesDoGerenciador(gerenciador, "combinacoes")
    sensores = NomesDoGerenciador(gerenciador, "sensores")
    Tentar gerenciador, "resultados"

    etapa = "ler os corpos da peca"
    Set corpos = CreateObject("Scripting.Dictionary")
    listaDeCorpos = swPeca.GetBodies2(CORPO_SOLIDO, False)
    If TemItens(listaDeCorpos) Then
        For Each corpo In listaDeCorpos
            If Not corpos.Exists(corpo.Name) Then corpos.Add corpo.Name, corpo
        Next corpo
    End If

    ' 1o caminho: a lista de vigas do estudo (os nomes "Viga-n(...)" do Simulation). Se alguma
    ' chamada nao responder nesta versao, 2o caminho: os corpos da peca, como no exemplo da API
    ' "Get Forces and Stresses for Selected Beams"; o que nao for viga (chapa) fica de fora sozinho.
    etapa = "ler a lista de vigas do estudo"
    motivo = ""
    totalDeVigas = LerVigasDoEstudo(estudo, corpos, nomesDasVigas, corposDasVigas, vigasDoEstudo, motivo)
    pelosCorpos = (totalDeVigas < 1)
    If pelosCorpos Then
        etapa = "usar os corpos da peca como vigas"
        If corpos.Count < 1 Then
            MsgBox "A peca nao tem corpos solidos e a lista de vigas do estudo nao respondeu (" & motivo & ").", vbExclamation
            Exit Sub
        End If
        totalDeVigas = corpos.Count
        ReDim nomesDasVigas(totalDeVigas - 1)
        ReDim corposDasVigas(totalDeVigas - 1)
        ReDim vigasDoEstudo(totalDeVigas - 1)
        j = 0
        For Each corpo In corpos.Keys
            nomesDasVigas(j) = "Viga-" & (j + 1) & "(" & CStr(corpo) & ")"
            Set corposDasVigas(j) = corpos(corpo)
            j = j + 1
        Next corpo
    End If
    ReDim ehViga(totalDeVigas - 1)
    For j = 0 To totalDeVigas - 1
        ehViga(j) = True
    Next j

    For i = LBound(casos) To UBound(casos)
        caso = CStr(casos(i))
        etapa = "carregar os resultados do caso " & caso
        If Not CarregarCaso(gerenciador, caso) Then
            Problema caso & " (sem resultados: Executar no gerenciador antes)"
        Else
            Set resultados = estudo.Results
            If resultados Is Nothing Then
                Problema caso & " (sem resultados: Executar no gerenciador antes)"
            Else
                etapa = "gravar as forcas das vigas do caso " & caso
                caminho = pasta & NomeDeArquivo(nomeDoEstudo & "-" & caso & "-forcas") & ".csv"
                arquivo = FreeFile
                Open caminho For Output As #arquivo
                CabecalhoDoCaso nomeDoEstudo, caso, quando
                Print #arquivo, "Nome da viga;Elemento;Fim;Axial (N);Cisalhamento1 (N);Cisalhamento2 (N);" & _
                    "Momento 1 (N.m);Momento 2 (N.m);Torque (N.m)"
                vigasExportadas = 0
                For j = 0 To totalDeVigas - 1
                    etapa = "ler os esforcos de " & nomesDasVigas(j) & " no caso " & caso
                    If Not ehViga(j) Then
                        ' Corpo que nao e viga no estudo (chapa, bloco): fica de fora.
                    ElseIf corposDasVigas(j) Is Nothing And vigasDoEstudo(j) Is Nothing Then
                        If Not jaClassificou Then Problema "viga " & (j + 1) & " (nao achada no estudo)"
                    ElseIf Not EsforcosDaViga(resultados, corposDasVigas(j), vigasDoEstudo(j), valores) Then
                        If pelosCorpos And Not jaClassificou Then
                            ehViga(j) = False
                            naoVigas = naoVigas + 1
                        ElseIf Not jaClassificou Then
                            Problema nomesDasVigas(j) & " (sem esforcos: " & ultimaFalha & ")"
                        End If
                    Else
                        Print #arquivo, NomeNoArquivo(nomesDasVigas(j), j) & ";;;;;;;;"
                        base = LBound(valores(0))
                        n = (UBound(valores(0)) - base + 1) \ 3
                        For e = 0 To n - 1
                            linha1 = ";" & Inteiro(valores(0)(base + 3 * e)) & ";1"
                            linha2 = ";;2"
                            For k = 0 To 5
                                linha1 = linha1 & ";" & NumLivre(valores(k)(LBound(valores(k)) + 3 * e + 1))
                                linha2 = linha2 & ";" & NumLivre(valores(k)(LBound(valores(k)) + 3 * e + 2))
                            Next k
                            Print #arquivo, linha1
                            Print #arquivo, linha2
                        Next e
                        vigasExportadas = vigasExportadas + 1
                    End If
                Next j
                Close #arquivo
                arquivo = 0
                jaClassificou = True

                etapa = "gravar as reacoes do caso " & caso
                If ReacoesDoModelo(resultados, soma) Then
                    caminho = pasta & NomeDeArquivo(nomeDoEstudo & "-" & caso & "-reacoes") & ".csv"
                    arquivo = FreeFile
                    Open caminho For Output As #arquivo
                    CabecalhoDoCaso nomeDoEstudo, caso, quando
                    base = LBound(soma)
                    Print #arquivo, "Forca de reacao (N)"
                    Print #arquivo, ""
                    Print #arquivo, "Componente;Selecao;Modelo inteiro"
                    Print #arquivo, "Soma X:;" & NumLivre(soma(base + 8)) & ";" & NumLivre(soma(base + 8))
                    Print #arquivo, "Soma Y:;" & NumLivre(soma(base + 9)) & ";" & NumLivre(soma(base + 9))
                    Print #arquivo, "Soma Z:;" & NumLivre(soma(base + 10)) & ";" & NumLivre(soma(base + 10))
                    Print #arquivo, "Resultante:;" & NumLivre(soma(base + 11)) & ";" & NumLivre(soma(base + 11))
                    Print #arquivo, ""
                    Print #arquivo, "Momento de reacao (N.m)"
                    Print #arquivo, ""
                    Print #arquivo, "Componente;Selecao;Modelo inteiro"
                    Print #arquivo, "Soma X:;" & NumLivre(soma(base + 12)) & ";" & NumLivre(soma(base + 12))
                    Print #arquivo, "Soma Y:;" & NumLivre(soma(base + 13)) & ";" & NumLivre(soma(base + 13))
                    Print #arquivo, "Soma Z:;" & NumLivre(soma(base + 14)) & ";" & NumLivre(soma(base + 14))
                    Print #arquivo, "Resultante:;" & NumLivre(soma(base + 15)) & ";" & NumLivre(soma(base + 15))
                    Close #arquivo
                    arquivo = 0
                Else
                    Problema caso & " (sem as reacoes: " & ultimaFalha & ")"
                End If
                If vigasExportadas > 0 Then casosExportados = casosExportados + 1
            End If
        End If
    Next i

    ' O quadro da Vista de resultados: cada sensor em cada caso e em cada combinacao.
    If TemItens(sensores) Then
        etapa = "gravar o quadro de resultados"
        caminho = pasta & NomeDeArquivo(nomeDoEstudo & "-gerenciador-resultados") & ".csv"
        arquivo = FreeFile
        Open caminho For Output As #arquivo
        Print #arquivo, "sep=;"
        Print #arquivo, "Nome do estudo:" & nomeDoEstudo
        Print #arquivo, "Quadro da Vista de resultados do gerenciador de casos de carga - valores como a API do SOLIDWORKS devolve"
        Print #arquivo, ""
        linha1 = "Caso;Tipo"
        For k = LBound(sensores) To UBound(sensores)
            linha1 = linha1 & ";" & CStr(sensores(k))
        Next k
        Print #arquivo, linha1
        For i = LBound(casos) To UBound(casos)
            Print #arquivo, LinhaDoQuadro(gerenciador, sensores, CStr(casos(i)), True)
        Next i
        If TemItens(combinacoes) Then
            For i = LBound(combinacoes) To UBound(combinacoes)
                Print #arquivo, LinhaDoQuadro(gerenciador, sensores, CStr(combinacoes(i)), False)
            Next i
        End If
        Close #arquivo
        arquivo = 0
    End If

    ' Resumo.
    Dim texto As String
    texto = casosExportados & " de " & (UBound(casos) - LBound(casos) + 1) & " casos primarios do estudo " & _
        nomeDoEstudo & " exportados (forcas das vigas e reacoes) para:" & vbCrLf & pasta
    If TemItens(sensores) Then texto = texto & vbCrLf & vbCrLf & "Quadro dos sensores: " & _
        NomeDeArquivo(nomeDoEstudo & "-gerenciador-resultados") & ".csv"
    If pelosCorpos Then
        texto = texto & vbCrLf & vbCrLf & "As vigas sairam pelos corpos da peca (a lista de vigas do " & _
            "Simulation nao respondeu: " & motivo & ")"
        If naoVigas > 0 Then texto = texto & "; " & naoVigas & " corpo(s) que nao sao viga no estudo ficaram de fora"
        texto = texto & "."
    End If
    If casosExportados = 0 And ultimaFalha <> "" Then
        texto = texto & vbCrLf & vbCrLf & "Nenhuma viga deu esforcos. Ultima falha: " & ultimaFalha
    End If
    texto = texto & vbCrLf & vbCrLf & "Envie os arquivos -forcas e -reacoes na pagina Esforcos do modelo."
    If totalProblemas > 0 Then
        texto = texto & vbCrLf & vbCrLf & "ATENCAO: " & totalProblemas & " item(ns) ficaram de fora: " & problemas
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
                descricaoDoErro & vbCrLf & vbCrLf & "O estudo nao foi alterado. Se repetir, mande esta " & _
                "mensagem.", vbExclamation
    End Select
End Sub

Function Suplemento(swApp As SldWorks.SldWorks) As Object
    ' O objeto do Simulation: o nome mudou entre as versoes do SOLIDWORKS.
    On Error Resume Next
    Set Suplemento = Nothing
    Set Suplemento = swApp.GetAddInObject("SldWorks.Simulation")
    If Suplemento Is Nothing Then Set Suplemento = swApp.GetAddInObject("CosmosWorks.CosmosWorks")
End Function

Sub Tentar(gerenciador As Object, acao As String)
    ' Abre o gerenciador e a Vista de resultados como o exemplo da API; se a versao nao tiver, segue.
    On Error Resume Next
    If acao = "abrir" Then
        gerenciador.OpenLoadCaseManager
    Else
        gerenciador.ShowResultsViewTab
    End If
    Err.Clear
End Sub

Function NomesDoGerenciador(gerenciador As Object, qual As String) As Variant
    On Error Resume Next
    NomesDoGerenciador = Empty
    If qual = "combinacoes" Then
        NomesDoGerenciador = gerenciador.GetAllLoadCaseCombinationNames()
    Else
        NomesDoGerenciador = gerenciador.GetAllTrackResultsSensorNames()
    End If
End Function

Function CarregarCaso(gerenciador As Object, caso As String) As Boolean
    On Error Resume Next
    CarregarCaso = False
    CarregarCaso = gerenciador.LoadResultsOfPrimaryLoadCase(caso)
    If Err.Number <> 0 Then CarregarCaso = False
End Function

Function LerVigasDoEstudo(estudo As Object, corpos As Object, nomes() As String, _
    corposDasVigas() As Object, vigas() As Object, motivo As String) As Long
    ' A lista de vigas do Simulation; 0 (e o motivo) se alguma chamada nao responder.
    Dim gerente As Object, viga As Object, total As Long, i As Long, erro As Long, passo As String
    On Error GoTo Falhou
    LerVigasDoEstudo = 0
    passo = "BeamManager"
    Set gerente = estudo.BeamManager
    If gerente Is Nothing Then
        motivo = "BeamManager vazio"
        Exit Function
    End If
    passo = "BeamCount"
    total = gerente.BeamCount
    If total < 1 Then
        motivo = "BeamCount = 0"
        Exit Function
    End If
    ReDim nomes(total - 1)
    ReDim corposDasVigas(total - 1)
    ReDim vigas(total - 1)
    For i = 0 To total - 1
        passo = "GetBeamBodyAt(" & i & ")"
        erro = 0
        Set viga = gerente.GetBeamBodyAt(i, erro)
        If viga Is Nothing Then
            motivo = passo & " vazio"
            Exit Function
        End If
        passo = "BeamBodyName"
        nomes(i) = viga.BeamBodyName
        Set vigas(i) = viga
        Set corposDasVigas(i) = CorpoDaViga(nomes(i), corpos)
    Next i
    LerVigasDoEstudo = total
    Exit Function
Falhou:
    motivo = passo & ": erro " & Err.Number & " (" & Err.Description & ")"
    LerVigasDoEstudo = 0
End Function

Function CorpoDaViga(nome As String, corpos As Object) As Object
    ' "Viga-1(U8""x17,1[5])" -> o corpo "U8""x17,1[5]" da peca; Nothing se nao achar.
    Dim dentro As String, abre As Long, fecha As Long
    Set CorpoDaViga = Nothing
    dentro = nome
    abre = InStr(nome, "(")
    fecha = InStrRev(nome, ")")
    If abre > 0 And fecha > abre Then dentro = Mid(nome, abre + 1, fecha - abre - 1)
    If corpos.Exists(dentro) Then
        Set CorpoDaViga = corpos(dentro)
    ElseIf corpos.Exists(nome) Then
        Set CorpoDaViga = corpos(nome)
    End If
End Function

Function EsforcosDaViga(resultados As Object, corpo As Object, viga As Object, valores() As Variant) As Boolean
    ' As seis listas (axial, cisalhamento 1 e 2, momento 1 e 2, torque): elemento, fim 1, fim 2...
    ' Tenta com o corpo da peca (como no exemplo da API) e, se nao der, com a viga do estudo.
    EsforcosDaViga = False
    If Not corpo Is Nothing Then
        If SeisListas(resultados, corpo, valores) Then
            EsforcosDaViga = True
            Exit Function
        End If
    End If
    If Not viga Is Nothing Then EsforcosDaViga = SeisListas(resultados, viga, valores)
End Function

Function SeisListas(resultados As Object, alvo As Object, valores() As Variant) As Boolean
    Dim selecao(0) As Object, entidades As Variant, k As Long, erro As Long
    On Error GoTo Falhou
    SeisListas = False
    Set selecao(0) = alvo
    entidades = selecao
    For k = 0 To 5
        erro = 0
        valores(k) = Empty
        valores(k) = resultados.GetBeamForcesForEntities(k, 1, (entidades), UNIDADES_SI, erro)
        If erro <> 0 Or Not TemItens(valores(k)) Then
            ultimaFalha = "GetBeamForcesForEntities devolveu o codigo " & erro
            Exit Function
        End If
    Next k
    For k = 1 To 5
        If UBound(valores(k)) - LBound(valores(k)) <> UBound(valores(0)) - LBound(valores(0)) Then Exit Function
    Next k
    SeisListas = ((UBound(valores(0)) - LBound(valores(0)) + 1) Mod 3 = 0)
    Exit Function
Falhou:
    ultimaFalha = "GetBeamForcesForEntities: erro " & Err.Number & " (" & Err.Description & ")"
    SeisListas = False
End Function

Function ReacoesDoModelo(resultados As Object, soma As Variant) As Boolean
    ' A soma das reacoes do modelo inteiro (posicoes 8 a 15 do segundo retorno).
    Dim cada As Variant, nos As Variant, vazio As Variant, erro As Long
    On Error Resume Next
    ReacoesDoModelo = False
    soma = Empty
    erro = 0
    nos = resultados.GetReactionForcesAndMomentsWithSelections(1, Nothing, FORCA_EM_N, vazio, soma, cada, erro)
    If Err.Number <> 0 Or erro <> 0 Or Not TemItens(soma) Then
        Err.Clear
        erro = 0
        vazio = Array()
        nos = resultados.GetReactionForcesAndMomentsWithSelections(1, Nothing, FORCA_EM_N, vazio, soma, cada, erro)
    End If
    If Err.Number <> 0 Or erro <> 0 Or Not TemItens(soma) Then
        ultimaFalha = "GetReactionForcesAndMomentsWithSelections: erro " & Err.Number & " " & _
            Err.Description & " / codigo " & erro
        Exit Function
    End If
    ReacoesDoModelo = (UBound(soma) - LBound(soma) + 1 >= 16)
End Function

Function LinhaDoQuadro(gerenciador As Object, sensores As Variant, nome As String, primario As Boolean) As String
    Dim k As Long, valor As Double, ok As Boolean, linha As String
    On Error Resume Next
    linha = nome & ";" & IIf(primario, "caso primario", "combinacao")
    For k = LBound(sensores) To UBound(sensores)
        valor = 0
        ok = False
        If primario Then
            ok = gerenciador.GetSensorResultValueForPrimaryLoadCase(CStr(sensores(k)), nome, valor)
        Else
            ok = gerenciador.GetSensorResultValueForLoadCaseCombination(CStr(sensores(k)), nome, valor)
        End If
        If Err.Number <> 0 Then
            ok = False
            Err.Clear
        End If
        linha = linha & ";" & IIf(ok, Replace(Format(valor, "0.000000E+00"), ".", ","), "")
    Next k
    LinhaDoQuadro = linha
End Function

Sub CabecalhoDoCaso(nomeDoEstudo As String, caso As String, quando As String)
    Print #arquivo, "sep=;"
    Print #arquivo, quando
    Print #arquivo, "Nome do estudo:" & nomeDoEstudo
    Print #arquivo, "Caso de carga: " & caso
    Print #arquivo, "Macro: Mecanica Toolkit - exportar_casos_de_carga " & VERSAO_DA_MACRO
    Print #arquivo, ""
End Sub

Sub Problema(texto As String)
    totalProblemas = totalProblemas + 1
    If totalProblemas <= 15 Then
        If problemas <> "" Then problemas = problemas & "; "
        problemas = problemas & texto
    ElseIf totalProblemas = 16 Then
        problemas = problemas & "; ..."
    End If
End Sub

Function TemItens(lista As Variant) As Boolean
    On Error Resume Next
    TemItens = False
    If IsArray(lista) Then TemItens = (UBound(lista) >= LBound(lista))
End Function

Function NomeNoArquivo(nome As String, indice As Long) As String
    ' Como o "Listar forcas da viga" escreve: Viga-1(nome do corpo). Ponto e virgula nao entra.
    Dim t As String
    t = Replace(nome, ";", ",")
    If Not (LCase(t) Like "viga-*" Or LCase(t) Like "beam-*") Then t = "Viga-" & (indice + 1) & "(" & t & ")"
    NomeNoArquivo = t
End Function

Function NomeDeArquivo(texto As String) As String
    Dim t As String, proibidos As Variant, c As Variant
    t = texto
    proibidos = Array("\", "/", ":", "*", "?", """", "<", ">", "|")
    For Each c In proibidos
        t = Replace(t, CStr(c), "_")
    Next c
    NomeDeArquivo = t
End Function

Function Inteiro(valor As Variant) As String
    On Error Resume Next
    Inteiro = CStr(valor)
    Inteiro = CStr(CLng(valor))
End Function

Function NumLivre(valor As Variant) As String
    ' Virgula decimal sempre, sem separador de milhar e sem zeros sobrando: -19606,1 e 4500.
    Dim t As String
    NumLivre = ""
    If IsEmpty(valor) Or IsNull(valor) Then Exit Function
    t = Replace(Format(CDbl(valor), "0.000000"), ".", ",")
    If InStr(t, ",") > 0 Then
        Do While Right(t, 1) = "0"
            t = Left(t, Len(t) - 1)
        Loop
        If Right(t, 1) = "," Then t = Left(t, Len(t) - 1)
    End If
    If t = "-0" Then t = "0"
    NumLivre = t
End Function
