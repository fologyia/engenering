' Mecanica Toolkit - exporta os resultados de cada caso do gerenciador de casos de carga do
' SOLIDWORKS Simulation para CSV: o que a Vista de resultados mostra, sem passar pelo relatorio.
'
' Uso (uma vez): com a peca aberta e a aba do estudo do gerenciador selecionada, Ferramentas >
' Macro > Nova..., de um nome e salve; no editor que abrir, apague tudo e cole este texto inteiro.
' Ainda no editor: Ferramentas > Referencias... e marque "SOLIDWORKS Simulation <ano> type
' library" (sem ela o editor acusa "Tipo definido pelo usuario nao definido"). Salve e tecle F5.
' Das proximas vezes: Ferramentas > Macro > Executar... e escolha a macro salva (a referencia fica
' gravada nela).
' Antes de rodar, Executar no gerenciador: a macro so le os resultados ja calculados (nao roda o
' estudo e nao muda nada nele).
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
' Velocidade: no primeiro caso a macro descobre com que entidade cada viga responde (o corpo da
' peca ou a viga do estudo) e, dali em diante, vai direto nela. O aviso final diz quanto tempo cada
' etapa levou. Os esforcos sao lidos viga a viga: pedir todas as vigas numa chamada so fechou o
' SOLIDWORKS (v4 e v5), e parar o redesenho da tela com um comando em andamento travou o
' Simulation ao carregar cada caso (v4). Nao volte a fazer nenhum dos dois.
' Ate a v7 o Simulation devolveu os esforcos de uma viga so para todas. A v8 testa, no primeiro
' caso, tres jeitos de indicar a viga (o corpo selecionado, o corpo direto, a viga do estudo) com
' duas vigas diferentes e fica com o primeiro que der numeros diferentes. Se nenhum der (o
' SOLIDWORKS do usuario: os dois primeiros repetem uma viga so e o terceiro da o codigo 6), a
' macro nao grava os -forcas, so as reacoes e o quadro; os esforcos das vigas saem pelo "Listar
' forcas da viga" de cada caso, que o programa le do mesmo jeito.
'
' Robustez: se algo der errado, a macro diz em que etapa parou e por que (arquivo aberto no Excel,
' pasta sem permissao...) e fecha os arquivos. Uma viga ou um caso sem resultados fica de fora e e
' listado no aviso final; os outros saem normalmente. Se a leitura de todas as vigas juntas nao
' bater, a macro le viga a viga. Os numeros saem com virgula decimal, qualquer que seja a
' configuracao regional do Windows.
Option Explicit

Const VERSAO_DA_MACRO As String = "v9"
Const PECA As Long = 1          ' swDocPART
Const CORPO_SOLIDO As Long = 0  ' swSolidBody
Const UNIDADES_SI As Long = 0   ' swsUnitSI: N e N.m
Const FORCA_EM_N As Long = 0    ' swsForceUnitNOrNm

Dim etapa As String
Dim arquivo As Integer
Dim problemas As String
Dim totalProblemas As Long
Dim ultimaFalha As String
Dim falhasDoGerenciador As String
Dim modelo As SldWorks.ModelDoc2
Dim jeito As Long  ' 0 a descobrir; 1 corpo selecionado; 2 corpo direto; 3 viga do estudo; -1 nenhum

Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swPeca As SldWorks.PartDoc
    Dim suplementoDoSimulation As CosmosWorksLib.CwAddincallback
    Dim simulation As CosmosWorksLib.COSMOSWORKS
    Dim documentoDoSimulation As CosmosWorksLib.CWModelDoc
    Dim gerenteDeEstudos As CosmosWorksLib.CWStudyManager
    Dim estudo As CosmosWorksLib.CWStudy
    Dim gerenciador As CosmosWorksLib.CWLoadCaseManager
    Dim resultados As CosmosWorksLib.CWResults
    Dim corpos As Object
    Dim listaDeCorpos As Variant
    Dim corpo As Variant
    Dim casos As Variant
    Dim combinacoes As Variant
    Dim sensores As Variant
    Dim nomesDasVigas() As String
    Dim corposDasVigas() As Object
    Dim vigasDoEstudo() As Object
    Dim alvos() As Object
    Dim ehViga() As Boolean
    Dim totalDeVigas As Long
    Dim valoresDaViga(5) As Variant
    Dim soma As Variant
    Dim i As Long, j As Long, k As Long
    Dim caso As String, pasta As String, nomeDoEstudo As String, quando As String
    Dim caminho As String, linha1 As String
    Dim casosExportados As Long, vigasExportadas As Long
    Dim motivo As String, pelosCorpos As Boolean, naoVigas As Long, jaClassificou As Boolean
    Dim inicio As Single, marca As Single
    Dim tCarregar As Single, tVigas As Single, tReacoes As Single, tQuadro As Single

    On Error GoTo Falha
    ' Um arquivo que ficou aberto numa execucao interrompida trava a proxima: fecha tudo antes.
    Close
    arquivo = 0
    problemas = ""
    totalProblemas = 0
    ultimaFalha = ""
    falhasDoGerenciador = ""
    jeito = 0
    inicio = Timer

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
    Set modelo = swModel
    pasta = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, "\"))
    quando = Format(Now, "hh:nn") & "; " & Format(Now, "dd/mm/yyyy")

    etapa = "ligar ao SOLIDWORKS Simulation"
    Set suplementoDoSimulation = Suplemento(swApp)
    If suplementoDoSimulation Is Nothing Then
        MsgBox "Ligue o suplemento SOLIDWORKS Simulation (Ferramentas > Suplementos) e rode de novo.", vbExclamation
        Exit Sub
    End If
    Set simulation = suplementoDoSimulation.COSMOSWORKS
    Set documentoDoSimulation = simulation.ActiveDoc
    If documentoDoSimulation Is Nothing Then
        MsgBox "O Simulation nao achou a peca ativa: clique na peca e rode de novo.", vbExclamation
        Exit Sub
    End If
    Set gerenteDeEstudos = documentoDoSimulation.StudyManager
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
    ReDim alvos(totalDeVigas - 1)
    For j = 0 To totalDeVigas - 1
        ehViga(j) = True
    Next j

    For i = LBound(casos) To UBound(casos)
        caso = CStr(casos(i))
        etapa = "carregar os resultados do caso " & caso
        DoEvents  ' devolve a vez ao SOLIDWORKS entre um caso e outro
        marca = Timer
        If Not CarregarCaso(gerenciador, caso) Then
            Problema caso & " (" & ultimaFalha & ")"
            tCarregar = tCarregar + (Timer - marca)
        Else
            Set resultados = estudo.Results
            tCarregar = tCarregar + (Timer - marca)
            If resultados Is Nothing Then
                Problema caso & " (sem resultados: Executar no gerenciador antes)"
            Else
                marca = Timer
                If jeito = 0 Then
                    etapa = "descobrir como o Simulation reconhece cada viga"
                    jeito = DescobrirJeito(resultados, corposDasVigas, vigasDoEstudo, totalDeVigas)
                    If jeito = 0 Then jeito = -1  ' a API nao separa as vigas: so reacoes e quadro
                End If
                If jeito > 0 Then
                etapa = "gravar as forcas das vigas do caso " & caso
                caminho = pasta & NomeDeArquivo(nomeDoEstudo & "-" & caso & "-forcas") & ".csv"
                arquivo = FreeFile
                Open caminho For Output As #arquivo
                CabecalhoDoCaso nomeDoEstudo, caso, quando
                Print #arquivo, "Nome da viga;Elemento;Fim;Axial (N);Cisalhamento1 (N);Cisalhamento2 (N);" & _
                    "Momento 1 (N.m);Momento 2 (N.m);Torque (N.m)"
                vigasExportadas = 0
                For j = 0 To totalDeVigas - 1
                    If ehViga(j) Then
                        etapa = "ler os esforcos de " & nomesDasVigas(j) & " no caso " & caso
                        If Not jaClassificou Then
                            ' No primeiro caso: com que entidade a viga responde.
                            If AlvoDaViga(resultados, corposDasVigas(j), vigasDoEstudo(j), alvos(j), valoresDaViga) Then
                                GravarDaViga NomeNoArquivo(nomesDasVigas(j), j), valoresDaViga
                                vigasExportadas = vigasExportadas + 1
                            Else
                                ehViga(j) = False
                                If corposDasVigas(j) Is Nothing And vigasDoEstudo(j) Is Nothing Then
                                    Problema "viga " & (j + 1) & " (nao achada no estudo)"
                                ElseIf pelosCorpos Then
                                    naoVigas = naoVigas + 1
                                Else
                                    Problema nomesDasVigas(j) & " (sem esforcos: " & ultimaFalha & ")"
                                End If
                            End If
                        ElseIf SeisListas(resultados, alvos(j), valoresDaViga) Then
                            GravarDaViga NomeNoArquivo(nomesDasVigas(j), j), valoresDaViga
                            vigasExportadas = vigasExportadas + 1
                        Else
                            Problema nomesDasVigas(j) & " no caso " & caso & " (sem esforcos: " & ultimaFalha & ")"
                        End If
                    End If
                Next j
                jaClassificou = True
                Close #arquivo
                arquivo = 0
                End If
                tVigas = tVigas + (Timer - marca)

                etapa = "gravar as reacoes do caso " & caso
                marca = Timer
                If ReacoesDoModelo(resultados, soma) Then
                    caminho = pasta & NomeDeArquivo(nomeDoEstudo & "-" & caso & "-reacoes") & ".csv"
                    arquivo = FreeFile
                    Open caminho For Output As #arquivo
                    CabecalhoDoCaso nomeDoEstudo, caso, quando
                    GravarReacoes soma
                    Close #arquivo
                    arquivo = 0
                Else
                    Problema caso & " (sem as reacoes: " & ultimaFalha & ")"
                End If
                tReacoes = tReacoes + (Timer - marca)
                If vigasExportadas > 0 Or jeito < 0 Then casosExportados = casosExportados + 1
            End If
        End If
    Next i

    On Error Resume Next
    modelo.ClearSelection2 True
    On Error GoTo Falha

    ' O quadro da Vista de resultados: cada sensor em cada caso e em cada combinacao.
    If TemItens(sensores) Then
        etapa = "gravar o quadro de resultados"
        marca = Timer
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
        tQuadro = Timer - marca
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
    If casosExportados = 0 And falhasDoGerenciador <> "" Then
        texto = texto & vbCrLf & vbCrLf & "No gerenciador: " & falhasDoGerenciador
    End If
    texto = texto & vbCrLf & vbCrLf & "Tempo: " & Segundos(Timer - inicio) & " (carregar os casos " & _
        Segundos(tCarregar) & "; esforcos das vigas " & Segundos(tVigas) & "; reacoes " & _
        Segundos(tReacoes) & "; quadro " & Segundos(tQuadro) & ")."
    If jeito < 0 Then
        texto = texto & vbCrLf & vbCrLf & "ESFORCOS DAS VIGAS: o Simulation desta versao devolve os mesmos " & _
            "esforcos para todas as vigas pela API, entao a macro nao gravou os -forcas (" & ultimaFalha & _
            "). Em cada caso: Vista de resultados, clique no caso, Resultados > Listar forcas da viga " & _
            "(todas as vigas) > Salvar, com o codigo do caso no nome (PP-forcas.csv). O programa le esses " & _
            "arquivos junto com os -reacoes desta macro."
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

Function Suplemento(swApp As SldWorks.SldWorks) As CosmosWorksLib.CwAddincallback
    ' O objeto do Simulation: o nome mudou entre as versoes do SOLIDWORKS.
    On Error Resume Next
    Set Suplemento = Nothing
    Set Suplemento = swApp.GetAddInObject("SldWorks.Simulation")
    If Suplemento Is Nothing Then Set Suplemento = swApp.GetAddInObject("CosmosWorks.CosmosWorks")
End Function

Sub Tentar(gerenciador As CosmosWorksLib.CWLoadCaseManager, acao As String)
    ' Abre o gerenciador e a Vista de resultados como o exemplo da API; se falhar, anota e segue.
    Dim ok As Boolean
    On Error Resume Next
    ok = True
    If acao = "abrir" Then
        ok = gerenciador.OpenLoadCaseManager()
    Else
        ok = gerenciador.ShowResultsViewTab()
    End If
    If Err.Number <> 0 Then
        falhasDoGerenciador = falhasDoGerenciador & IIf(acao = "abrir", "OpenLoadCaseManager", _
            "ShowResultsViewTab") & ": erro " & Err.Number & " (" & Err.Description & "); "
    ElseIf Not ok Then
        falhasDoGerenciador = falhasDoGerenciador & IIf(acao = "abrir", "OpenLoadCaseManager", _
            "ShowResultsViewTab") & " devolveu Falso; "
    End If
    Err.Clear
End Sub

Function NomesDoGerenciador(gerenciador As CosmosWorksLib.CWLoadCaseManager, qual As String) As Variant
    On Error Resume Next
    NomesDoGerenciador = Empty
    If qual = "combinacoes" Then
        NomesDoGerenciador = gerenciador.GetAllLoadCaseCombinationNames()
    Else
        NomesDoGerenciador = gerenciador.GetAllTrackResultsSensorNames()
    End If
End Function

Function CarregarCaso(gerenciador As CosmosWorksLib.CWLoadCaseManager, caso As String) As Boolean
    On Error Resume Next
    CarregarCaso = False
    CarregarCaso = gerenciador.LoadResultsOfPrimaryLoadCase(caso)
    If Err.Number <> 0 Then
        ultimaFalha = "LoadResultsOfPrimaryLoadCase: erro " & Err.Number & " (" & Err.Description & ")"
        CarregarCaso = False
    ElseIf Not CarregarCaso Then
        ultimaFalha = "LoadResultsOfPrimaryLoadCase devolveu Falso: Executar no gerenciador antes"
    End If
End Function

Function LerVigasDoEstudo(estudo As CosmosWorksLib.CWStudy, corpos As Object, nomes() As String, _
    corposDasVigas() As Object, vigas() As Object, motivo As String) As Long
    ' A lista de vigas do Simulation; 0 (e o motivo) se alguma chamada nao responder.
    Dim gerente As CosmosWorksLib.CWBeamManager, viga As CosmosWorksLib.CWBeamBody
    Dim total As Long, i As Long, erro As Long, passo As String
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

Function UmaLista(resultados As CosmosWorksLib.CWResults, alvo As Object, componente As Long, _
    lista As Variant) As Boolean
    ' Um esforco (0 axial, 1 e 2 cisalhamento, 3 e 4 momento, 5 torque) de uma viga:
    ' elemento, fim 1, fim 2, elemento, fim 1, fim 2...
    Dim selecao(0) As Object, entidades As Variant, erro As Long
    On Error GoTo Falhou
    UmaLista = False
    If jeito = 1 Then
        Set selecao(0) = Selecionada(alvo)
    Else
        Set selecao(0) = alvo
    End If
    entidades = selecao
    erro = 0
    lista = Empty
    lista = resultados.GetBeamForcesForEntities(componente, 1, (entidades), UNIDADES_SI, erro)
    If erro <> 0 Or Not TemItens(lista) Then
        ultimaFalha = "GetBeamForcesForEntities devolveu o codigo " & erro
        Exit Function
    End If
    UmaLista = ((UBound(lista) - LBound(lista) + 1) Mod 3 = 0)
    Exit Function
Falhou:
    ultimaFalha = "GetBeamForcesForEntities: erro " & Err.Number & " (" & Err.Description & ")"
    UmaLista = False
End Function

Function Selecionada(alvo As Object) As Object
    ' Seleciona o corpo no modelo e devolve o objeto que a selecao entrega - e esse que a API
    ' reconhece como a viga. Se nao der para selecionar, vai o proprio alvo.
    Dim corpo As SldWorks.Body2, objeto As Object
    On Error Resume Next
    Set Selecionada = alvo
    If modelo Is Nothing Or Not TypeOf alvo Is SldWorks.Body2 Then Exit Function
    Set corpo = alvo
    modelo.ClearSelection2 True
    If corpo.Select2(False, Nothing) Then
        Set objeto = modelo.SelectionManager.GetSelectedObject6(1, -1)
        If Not objeto Is Nothing Then Set Selecionada = objeto
    End If
    Err.Clear
End Function

Function AlvoDaViga(resultados As CosmosWorksLib.CWResults, corpo As Object, viga As Object, _
    alvo As Object, valores() As Variant) As Boolean
    ' Os seis esforcos da viga pelo corpo da peca (como no exemplo da API) ou, se nao der, pela
    ' viga do estudo; alvo fica com a entidade que respondeu, para os casos seguintes.
    Set alvo = Nothing
    If jeito = 3 Then
        If Not viga Is Nothing Then
            If SeisListas(resultados, viga, valores) Then Set alvo = viga
        End If
    ElseIf Not corpo Is Nothing Then
        If SeisListas(resultados, corpo, valores) Then Set alvo = corpo
    End If
    AlvoDaViga = Not alvo Is Nothing
End Function

Function DescobrirJeito(resultados As CosmosWorksLib.CWResults, corpos() As Object, vigas() As Object, _
    total As Long) As Long
    ' Com duas vigas diferentes, o primeiro jeito de indicar a viga que da esforcos diferentes.
    Dim a As Long, b As Long, j As Long, tentativa As Long
    Dim listaA As Variant, listaB As Variant, alvoA As Object, alvoB As Object
    DescobrirJeito = 0
    a = -1
    b = -1
    For j = 0 To total - 1
        If Not corpos(j) Is Nothing Or Not vigas(j) Is Nothing Then
            If a < 0 Then
                a = j
            ElseIf b < 0 Then
                b = j
            End If
        End If
    Next j
    If a < 0 Or b < 0 Then
        DescobrirJeito = 2  ' uma viga so: nao ha o que comparar
        Exit Function
    End If
    For tentativa = 1 To 3
        jeito = tentativa
        If tentativa = 3 Then
            Set alvoA = vigas(a)
            Set alvoB = vigas(b)
        Else
            Set alvoA = corpos(a)
            Set alvoB = corpos(b)
        End If
        If Not alvoA Is Nothing And Not alvoB Is Nothing Then
            If UmaLista(resultados, alvoA, 0, listaA) And UmaLista(resultados, alvoB, 0, listaB) Then
                If Diferentes(listaA, listaB) Then
                    DescobrirJeito = tentativa
                    Exit Function
                End If
                ultimaFalha = "jeito " & tentativa & ": as duas vigas deram os mesmos esforcos"
            End If
        End If
    Next tentativa
    jeito = 0
End Function

Function Diferentes(a As Variant, b As Variant) As Boolean
    Dim k As Long
    Diferentes = True
    If UBound(a) - LBound(a) <> UBound(b) - LBound(b) Then Exit Function
    For k = 0 To UBound(a) - LBound(a)
        If Abs(CDbl(a(LBound(a) + k)) - CDbl(b(LBound(b) + k))) > 0.000001 Then Exit Function
    Next k
    Diferentes = False
End Function

Function SeisListas(resultados As CosmosWorksLib.CWResults, alvo As Object, valores() As Variant) As Boolean
    ' Os seis esforcos de uma viga, um a um (quando a leitura de todas juntas nao bate).
    Dim k As Long
    SeisListas = False
    If alvo Is Nothing Then Exit Function
    For k = 0 To 5
        If Not UmaLista(resultados, alvo, k, valores(k)) Then Exit Function
    Next k
    For k = 1 To 5
        If UBound(valores(k)) - LBound(valores(k)) <> UBound(valores(0)) - LBound(valores(0)) Then Exit Function
    Next k
    SeisListas = True
End Function

Sub GravarDaViga(nome As String, valores() As Variant)
    ' A viga a partir das seis listas dela.
    Dim e As Long, n As Long, k As Long, linha1 As String, linha2 As String
    Print #arquivo, nome & ";;;;;;;;"
    n = (UBound(valores(0)) - LBound(valores(0)) + 1) \ 3
    For e = 0 To n - 1
        linha1 = ";" & Inteiro(valores(0)(LBound(valores(0)) + 3 * e)) & ";1"
        linha2 = ";;2"
        For k = 0 To 5
            linha1 = linha1 & ";" & NumLivre(valores(k)(LBound(valores(k)) + 3 * e + 1))
            linha2 = linha2 & ";" & NumLivre(valores(k)(LBound(valores(k)) + 3 * e + 2))
        Next k
        Print #arquivo, linha1
        Print #arquivo, linha2
    Next e
End Sub

Function ReacoesDoModelo(resultados As CosmosWorksLib.CWResults, soma As Variant) As Boolean
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

Sub GravarReacoes(soma As Variant)
    Dim base As Long
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
End Sub

Function LinhaDoQuadro(gerenciador As CosmosWorksLib.CWLoadCaseManager, sensores As Variant, _
    nome As String, primario As Boolean) As String
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

Function Segundos(ByVal valor As Single) As String
    If valor < 0 Then valor = valor + 86400  ' passou da meia-noite
    Segundos = Replace(Format(valor, "0.0"), ".", ",") & " s"
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
