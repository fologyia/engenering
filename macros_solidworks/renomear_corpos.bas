' Mecanica Toolkit - renomeia os corpos da peca pelo arquivo de nomes do programa.
'
' Le o <peca>_nomes.csv que a pagina "Nomes das barras" do Mecanica Toolkit gera e da a cada corpo
' o nome novo, no padrao que o programa entende (P-A1 pilar, V-N1-A1-A2 viga, C-N0-B1-B2
' contraventamento, LG longarina, PS chapa de piso...). Grava tambem o PERFIL de cada item da
' lista de corte, quando o arquivo traz.
'
' Uso (uma vez): com a peca aberta, Ferramentas > Macro > Nova..., de um nome e salve; no editor
' que abrir, apague tudo, cole este texto inteiro e tecle F5.
' Das proximas vezes: Ferramentas > Macro > Executar... e escolha a macro salva.
'
' Onde ela procura o arquivo: ao lado da peca (<peca>_nomes.csv), depois na pasta Downloads; se
' nao achar, pede o caminho.
'
' Seguranca:
' - Nada muda sem a sua confirmacao: antes, a macro mostra o que vai trocar e o que vai pular.
' - Cada corpo e conferido pela geometria (centro de massa na linha de centro do esqueleto, volume)
'   antes de trocar: um nome [n] que passou para outro corpo depois de uma edicao nao engana. Se o
'   nome atual nao existe mais, o corpo e achado pela geometria; se nao da para ter certeza, pula.
' - Os nomes trocam em duas fases (primeiro um nome provisorio): dois corpos podem trocar de nome
'   entre si. Um corpo que o SolidWorks recusa volta ao nome antigo.
' - Depois de trocar, a peca e reconstruida e os nomes sao conferidos de novo.
'
' Saem dois arquivos ao lado da peca:
' - <peca>_nomes_aplicados.csv: o relatorio (envie na pagina Nomes das barras);
' - <peca>_nomes_desfazer.csv: rode a macro com ele (renomeie para <peca>_nomes.csv ou indique o
'   caminho) para voltar os nomes e os perfis de antes.
' Depois: salve a peca e rode exportar_lista_de_corte de novo (o esqueleto sai com os nomes novos).
' Estudos do Simulation ja rodados guardam os nomes antigos ate refazer a malha: o programa acha
' cada corpo mesmo assim, mas o certo e refazer a malha e rodar os estudos de novo.
Option Explicit

Const VERSAO_DA_MACRO As String = "v1"
Const MARCA_DO_ARQUIVO As String = "nomes das barras"
Const PROPRIEDADE_DO_PERFIL As String = "PERFIL"
Const DENSIDADE_ACO As Double = 7850#
Const TOLERANCIA_DO_CENTRO As Double = 0.005
Const TOLERANCIA_DO_VOLUME As Double = 0.01
Const TAMANHO_MAXIMO As Long = 255
Const TIPO_TEXTO As Long = 30
Const SUBSTITUIR_VALOR As Long = 2

' As linhas de corpo do arquivo de nomes.
Dim totalLinhas As Long
Dim atuais() As String
Dim novos() As String
Dim restos() As String
Dim pontas() As Double
Dim volumes() As Double
Dim alvos() As Long
Dim pelaGeometria() As Boolean
Dim situacoes() As String
Dim motivos() As String

' As linhas de perfil.
Dim totalPerfis As Long
Dim itensDoPerfil() As String
Dim valoresDoPerfil() As String
Dim corposDoPerfil() As String
Dim situacoesDoPerfil() As String
Dim motivosDoPerfil() As String
Dim perfisAntigos() As String

' Os corpos da peca.
Dim todosOsCorpos As Variant
Dim totalCorpos As Long
Dim nomesDosCorpos() As String
Dim centros() As Double
Dim volumesDosCorpos() As Double
Dim usados() As Boolean

Dim etapa As String
Dim marcaDoArquivo As String
Dim pecaDoArquivo As String
Dim configuracaoDoArquivo As String

Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swPart As SldWorks.PartDoc
    Dim swCorpo As SldWorks.Body2
    On Error GoTo Falha
    ' Um arquivo que ficou aberto numa execucao interrompida trava a proxima: fecha tudo antes.
    Close

    etapa = "abrir a peca"
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        MsgBox "Abra a peca (o arquivo da estrutura) antes de rodar a macro.", vbExclamation
        Exit Sub
    End If
    If swModel.GetType <> swDocPART Then
        MsgBox "A macro renomeia os corpos de uma PECA. Abra o arquivo da peca, nao o desenho nem a montagem.", vbExclamation
        Exit Sub
    End If
    If swModel.GetPathName = "" Then
        MsgBox "Salve a peca antes: o arquivo de nomes e os relatorios ficam na pasta dela.", vbExclamation
        Exit Sub
    End If
    Set swPart = swModel

    ' 1) O arquivo de nomes.
    Dim base As String, peca As String, nomeBase As String, caminho As String
    base = Left(swModel.GetPathName, InStrRev(swModel.GetPathName, ".") - 1)
    peca = Mid(swModel.GetPathName, InStrRev(swModel.GetPathName, "\") + 1)
    nomeBase = Mid(base, InStrRev(base, "\") + 1)
    etapa = "achar o arquivo de nomes"
    caminho = ArquivoDeNomes(base, nomeBase)
    If caminho = "" Then Exit Sub
    etapa = "ler " & caminho
    LerArquivo caminho
    If InStr(1, LCase(marcaDoArquivo), MARCA_DO_ARQUIVO) = 0 Then
        MsgBox "O arquivo " & caminho & " nao e o arquivo de nomes do Mecanica Toolkit." & vbCrLf & vbCrLf & _
            "Baixe-o na pagina Nomes das barras e rode a macro de novo.", vbExclamation
        Exit Sub
    End If
    If totalLinhas = 0 And totalPerfis = 0 Then
        MsgBox "O arquivo " & caminho & " nao pede nenhuma troca: os nomes ja estao no padrao.", vbInformation
        Exit Sub
    End If
    Dim resposta As Long
    If pecaDoArquivo <> "" And LCase(pecaDoArquivo) <> LCase(peca) Then
        resposta = MsgBox("O arquivo de nomes foi feito para a peca " & pecaDoArquivo & ", e a peca aberta e " & _
            peca & "." & vbCrLf & vbCrLf & "A macro confere cada corpo pela geometria, mas o certo e usar o " & _
            "arquivo desta peca. Continuar mesmo assim?", vbYesNo + vbExclamation + vbDefaultButton2)
        If resposta <> vbYes Then Exit Sub
    End If

    ' 2) Os corpos da peca: nome, centro de massa e volume.
    etapa = "ler os corpos da peca"
    todosOsCorpos = swPart.GetBodies2(swSolidBody, False)
    If Not IsArray(todosOsCorpos) Then
        MsgBox "A peca nao tem corpos solidos.", vbExclamation
        Exit Sub
    End If
    Dim porNome As Object
    Set porNome = CreateObject("Scripting.Dictionary")
    porNome.CompareMode = vbTextCompare
    Dim k As Long, i As Long, vMassa As Variant
    totalCorpos = UBound(todosOsCorpos) + 1
    ReDim nomesDosCorpos(totalCorpos - 1)
    ReDim centros(3 * totalCorpos - 1)
    ReDim volumesDosCorpos(totalCorpos - 1)
    ReDim usados(totalCorpos - 1)
    For k = 0 To totalCorpos - 1
        Set swCorpo = todosOsCorpos(k)
        nomesDosCorpos(k) = swCorpo.Name
        If Not porNome.Exists(nomesDosCorpos(k)) Then porNome.Add nomesDosCorpos(k), k
        vMassa = Massa(swCorpo)
        If IsArray(vMassa) Then
            centros(3 * k) = vMassa(0)
            centros(3 * k + 1) = vMassa(1)
            centros(3 * k + 2) = vMassa(2)
            volumesDosCorpos(k) = vMassa(3)
        Else
            volumesDosCorpos(k) = -1#
        End If
    Next k

    ' 3) Cada linha no seu corpo: pelo nome (conferido pela geometria), depois so pela geometria.
    etapa = "achar os corpos do arquivo"
    If totalLinhas > 0 Then
        ReDim alvos(totalLinhas - 1)
        ReDim pelaGeometria(totalLinhas - 1)
        ReDim situacoes(totalLinhas - 1)
        ReDim motivos(totalLinhas - 1)
    End If
    For i = 0 To totalLinhas - 1
        alvos(i) = -1
        If porNome.Exists(atuais(i)) Then
            k = porNome(atuais(i))
            If Not usados(k) Then
                If Confere(k, i) Then
                    alvos(i) = k
                    usados(k) = True
                End If
            End If
        End If
    Next i
    For i = 0 To totalLinhas - 1
        If alvos(i) < 0 Then
            k = PelaGeometriaDoCorpo(i)
            If k >= 0 Then
                alvos(i) = k
                usados(k) = True
                pelaGeometria(i) = True
                motivos(i) = "no arquivo, " & atuais(i)
            ElseIf k = -2 Then
                situacoes(i) = "PULADO"
                motivos(i) = "mais de um corpo no lugar do corpo do esqueleto: gere o esqueleto de novo"
            Else
                situacoes(i) = "PULADO"
                motivos(i) = "o corpo nao esta mais na peca, ou mudou de lugar ou de tamanho: gere o esqueleto de novo"
            End If
        End If
    Next i

    ' 4) Os nomes novos: no padrao, sem repetir e sem tomar o nome de um corpo que fica.
    etapa = "conferir os nomes novos"
    For i = 0 To totalLinhas - 1
        If situacoes(i) = "" Then
            If StrComp(nomesDosCorpos(alvos(i)), novos(i), vbBinaryCompare) = 0 Then
                situacoes(i) = "JA TINHA O NOME"
            ElseIf Not NomeValido(novos(i)) Then
                situacoes(i) = "PULADO"
                motivos(i) = "nome novo que o SolidWorks nao aceita (vazio, com arroba ou longo demais)"
            Else
                situacoes(i) = "A TROCAR"
            End If
        End If
    Next i
    Dim mudou As Boolean, ficam As Object, pedidos As Object, voltas As Long
    Do
        mudou = False
        voltas = voltas + 1
        Set ficam = CreateObject("Scripting.Dictionary")
        ficam.CompareMode = vbTextCompare
        For k = 0 To totalCorpos - 1
            If Not usados(k) Then
                If Not ficam.Exists(nomesDosCorpos(k)) Then ficam.Add nomesDosCorpos(k), k
            End If
        Next k
        For i = 0 To totalLinhas - 1
            If alvos(i) >= 0 And situacoes(i) <> "A TROCAR" Then
                If Not ficam.Exists(nomesDosCorpos(alvos(i))) Then ficam.Add nomesDosCorpos(alvos(i)), alvos(i)
            End If
        Next i
        Set pedidos = CreateObject("Scripting.Dictionary")
        pedidos.CompareMode = vbTextCompare
        For i = 0 To totalLinhas - 1
            If situacoes(i) = "A TROCAR" Then
                If ficam.Exists(novos(i)) Then
                    situacoes(i) = "PULADO"
                    motivos(i) = "o nome " & novos(i) & " ja e de outro corpo, que fica como esta"
                    mudou = True
                ElseIf pedidos.Exists(novos(i)) Then
                    situacoes(i) = "PULADO"
                    motivos(i) = "o mesmo nome novo para dois corpos"
                    mudou = True
                Else
                    pedidos.Add novos(i), i
                End If
            End If
        Next i
    Loop While mudou And voltas < 50

    ' 5) Os perfis: cada item da lista de corte pelo corpo dele (ou pelo nome do item).
    etapa = "ler a lista de corte"
    Dim pastas As New Collection, pastaDoCorpo As Object
    Set pastaDoCorpo = CreateObject("Scripting.Dictionary")
    pastaDoCorpo.CompareMode = vbTextCompare
    If totalPerfis > 0 Then JuntarPastas swModel, pastas, pastaDoCorpo
    Dim indicesDasPastas() As Long
    If totalPerfis > 0 Then ReDim indicesDasPastas(totalPerfis - 1)
    For i = 0 To totalPerfis - 1
        indicesDasPastas(i) = 0
        If pastaDoCorpo.Exists(corposDoPerfil(i)) Then
            indicesDasPastas(i) = pastaDoCorpo(corposDoPerfil(i))
        Else
            For k = 1 To pastas.Count
                If StrComp(pastas(k).Name, itensDoPerfil(i), vbTextCompare) = 0 Then indicesDasPastas(i) = k
            Next k
        End If
        If indicesDasPastas(i) = 0 Then
            situacoesDoPerfil(i) = "PULADO"
            motivosDoPerfil(i) = "o item nao esta mais na lista de corte"
        Else
            perfisAntigos(i) = ValorDoPerfil(pastas(indicesDasPastas(i)))
            If perfisAntigos(i) = valoresDoPerfil(i) Then
                situacoesDoPerfil(i) = "JA TINHA"
            Else
                situacoesDoPerfil(i) = "A GRAVAR"
            End If
        End If
    Next i

    ' 6) A confirmacao.
    etapa = "pedir a confirmacao"
    Dim aTrocar As Long, pelaGeo As Long, jaTinham As Long, pulados As Long, aGravar As Long
    Dim exemplos As String, motivosDosPulos As String
    For i = 0 To totalLinhas - 1
        Select Case situacoes(i)
            Case "A TROCAR"
                aTrocar = aTrocar + 1
                If pelaGeometria(i) Then pelaGeo = pelaGeo + 1
                If aTrocar <= 8 Then exemplos = exemplos & "   " & nomesDosCorpos(alvos(i)) & "  ->  " & novos(i) & vbCrLf
            Case "JA TINHA O NOME"
                jaTinham = jaTinham + 1
            Case Else
                pulados = pulados + 1
                If pulados <= 4 Then motivosDosPulos = motivosDosPulos & "   " & atuais(i) & ": " & motivos(i) & vbCrLf
        End Select
    Next i
    For i = 0 To totalPerfis - 1
        If situacoesDoPerfil(i) = "A GRAVAR" Then aGravar = aGravar + 1
    Next i
    If aTrocar = 0 And aGravar = 0 Then
        MsgBox "Nada a trocar: " & jaTinham & " corpo(s) ja tem o nome e " & pulados & " foram pulados." & _
            vbCrLf & vbCrLf & motivosDosPulos, vbExclamation
        Exit Sub
    End If
    Dim texto As String
    texto = "Arquivo: " & caminho & vbCrLf & vbCrLf
    texto = texto & aTrocar & " corpo(s) mudam de nome"
    If pelaGeo > 0 Then texto = texto & " (" & pelaGeo & " achados pela geometria)"
    texto = texto & vbCrLf & exemplos
    If aTrocar > 8 Then texto = texto & "   ..." & vbCrLf
    If jaTinham > 0 Then texto = texto & jaTinham & " ja tem o nome." & vbCrLf
    If aGravar > 0 Then texto = texto & aGravar & " item(ns) da lista de corte recebem o PERFIL." & vbCrLf
    If pulados > 0 Then texto = texto & vbCrLf & pulados & " pulado(s):" & vbCrLf & motivosDosPulos
    If configuracaoDoArquivo <> "" And configuracaoDoArquivo <> NomeDaConfiguracao(swModel) Then
        texto = texto & vbCrLf & "ATENCAO: o esqueleto e da configuracao " & configuracaoDoArquivo & _
            "; a ativa e " & NomeDaConfiguracao(swModel) & "." & vbCrLf
    End If
    texto = texto & vbCrLf & "Trocar agora?"
    resposta = MsgBox(texto, vbYesNo + vbQuestion, "Renomear os corpos")
    If resposta <> vbYes Then Exit Sub

    ' 7) Os perfis (antes dos nomes: o corpo de cada item ainda tem o nome do arquivo).
    etapa = "gravar o PERFIL dos itens da lista de corte"
    For i = 0 To totalPerfis - 1
        If situacoesDoPerfil(i) = "A GRAVAR" Then
            If GravarPerfil(pastas(indicesDasPastas(i)), valoresDoPerfil(i)) Then
                If valoresDoPerfil(i) = "" Then
                    situacoesDoPerfil(i) = "APAGADO"
                Else
                    situacoesDoPerfil(i) = "GRAVADO"
                End If
            Else
                situacoesDoPerfil(i) = "PULADO"
                motivosDoPerfil(i) = "o SolidWorks nao aceitou gravar a propriedade"
            End If
        End If
    Next i

    ' 8) Os nomes, em duas fases: primeiro um nome provisorio, depois o novo.
    etapa = "dar os nomes provisorios"
    Dim provisorio As String
    For i = 0 To totalLinhas - 1
        If situacoes(i) = "A TROCAR" Then
            Set swCorpo = todosOsCorpos(alvos(i))
            provisorio = NomeProvisorio(i, porNome)
            If Renomear(swCorpo, provisorio) Then
                situacoes(i) = "PROVISORIO"
            Else
                situacoes(i) = "PULADO"
                motivos(i) = "o SolidWorks nao aceitou trocar o nome deste corpo"
            End If
        End If
    Next i
    etapa = "dar os nomes novos"
    For i = 0 To totalLinhas - 1
        If situacoes(i) = "PROVISORIO" Then
            Set swCorpo = todosOsCorpos(alvos(i))
            If Renomear(swCorpo, novos(i)) Then
                If pelaGeometria(i) Then
                    situacoes(i) = "RENOMEADO PELA GEOMETRIA"
                Else
                    situacoes(i) = "RENOMEADO"
                End If
            Else
                situacoes(i) = "PULADO"
                motivos(i) = "o SolidWorks nao aceitou o nome " & novos(i)
                If Not Renomear(swCorpo, nomesDosCorpos(alvos(i))) Then
                    motivos(i) = motivos(i) & "; o corpo ficou com o nome provisorio " & swCorpo.Name
                End If
            End If
        End If
    Next i

    ' 9) Reconstroi e confere: um nome que o SolidWorks voltou aparece como pulado.
    etapa = "reconstruir a peca"
    swModel.ForceRebuild3 False
    etapa = "conferir os nomes depois da reconstrucao"
    Dim vDepois As Variant, depois As Object
    Set depois = CreateObject("Scripting.Dictionary")
    vDepois = swPart.GetBodies2(swSolidBody, False)
    If IsArray(vDepois) Then
        For k = 0 To UBound(vDepois)
            Set swCorpo = vDepois(k)
            If Not depois.Exists(swCorpo.Name) Then depois.Add swCorpo.Name, k
        Next k
    End If
    Dim trocados As Long
    For i = 0 To totalLinhas - 1
        If Left(situacoes(i), 9) = "RENOMEADO" Then
            If depois.Exists(novos(i)) Then
                trocados = trocados + 1
            Else
                situacoes(i) = "PULADO"
                motivos(i) = "o SolidWorks voltou o nome ao reconstruir a peca"
            End If
        End If
    Next i
    AtualizarArvore swModel

    ' 10) O relatorio e o arquivo para desfazer.
    Dim caminhoRelatorio As String, caminhoDesfazer As String, quando As String
    quando = Format(Now, "yyyy-mm-dd hh:nn")
    caminhoRelatorio = base & "_nomes_aplicados.csv"
    caminhoDesfazer = base & "_nomes_desfazer.csv"
    etapa = "gravar " & caminhoRelatorio
    GravarRelatorio caminhoRelatorio, peca, NomeDaConfiguracao(swModel), quando, caminho
    etapa = "gravar " & caminhoDesfazer
    GravarDesfazer caminhoDesfazer, peca, NomeDaConfiguracao(swModel), quando

    ' 11) Resumo.
    Dim gravados As Long, puladosNoFim As Long
    For i = 0 To totalPerfis - 1
        If situacoesDoPerfil(i) = "GRAVADO" Or situacoesDoPerfil(i) = "APAGADO" Then gravados = gravados + 1
    Next i
    For i = 0 To totalLinhas - 1
        If situacoes(i) = "PULADO" Then puladosNoFim = puladosNoFim + 1
    Next i
    texto = trocados & " corpo(s) renomeado(s)"
    If gravados > 0 Then texto = texto & " e " & gravados & " PERFIL(is) gravado(s)"
    texto = texto & "." & vbCrLf & vbCrLf & "Relatorio (envie na pagina Nomes das barras):" & vbCrLf & _
        caminhoRelatorio & vbCrLf & vbCrLf & "Para voltar os nomes antigos, rode a macro com:" & vbCrLf & _
        caminhoDesfazer & vbCrLf & vbCrLf & "Agora: SALVE a peca e rode exportar_lista_de_corte de novo. " & _
        "Se os estudos do Simulation ja foram rodados, refaca a malha e rode de novo."
    If puladosNoFim > 0 Then
        texto = texto & vbCrLf & vbCrLf & "ATENCAO: " & puladosNoFim & " corpo(s) pulado(s); o motivo de cada um esta no relatorio."
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
                descricaoDoErro & vbCrLf & vbCrLf & "Confira os nomes na arvore: o que ja trocou fica " & _
                "trocado. Se repetir, mande esta mensagem junto com o arquivo de nomes.", vbExclamation
    End Select
End Sub

Function ArquivoDeNomes(base As String, nomeBase As String) As String
    ' Ao lado da peca, depois na pasta Downloads; senao, o caminho que a pessoa colar.
    Dim candidato As String, pasta As String
    ArquivoDeNomes = ""
    candidato = base & "_nomes.csv"
    If Existe(candidato) Then
        ArquivoDeNomes = candidato
        Exit Function
    End If
    pasta = Environ("USERPROFILE") & "\Downloads\"
    If Existe(pasta & nomeBase & "_nomes.csv") Then
        ArquivoDeNomes = pasta & nomeBase & "_nomes.csv"
        Exit Function
    End If
    candidato = InputBox("Nao achei " & nomeBase & "_nomes.csv ao lado da peca nem na pasta Downloads." & _
        vbCrLf & vbCrLf & "Baixe o arquivo na pagina Nomes das barras do Mecanica Toolkit e salve-o na " & _
        "pasta da peca, ou cole abaixo o caminho completo dele:", "Arquivo de nomes", base & "_nomes.csv")
    candidato = Trim(Replace(candidato, """", ""))
    If candidato = "" Then Exit Function
    If Not Existe(candidato) Then
        MsgBox "O arquivo " & candidato & " nao existe.", vbExclamation
        Exit Function
    End If
    ArquivoDeNomes = candidato
End Function

Function Existe(caminho As String) As Boolean
    On Error Resume Next
    Existe = False
    Existe = (Len(Dir(caminho, vbNormal)) > 0)
End Function

Sub LerArquivo(caminho As String)
    ' As linhas de metadados, de corpo (CORPO) e de perfil (PERFIL); o resto e ignorado.
    Dim numeroDoArquivo As Integer, linha As String, partes As Variant, chave As String
    totalLinhas = 0
    totalPerfis = 0
    marcaDoArquivo = ""
    pecaDoArquivo = ""
    configuracaoDoArquivo = ""
    numeroDoArquivo = FreeFile
    Open caminho For Input As #numeroDoArquivo
    Do While Not EOF(numeroDoArquivo)
        Line Input #numeroDoArquivo, linha
        partes = DividirLinha(linha)
        chave = UCase(Trim(partes(0)))
        Select Case chave
            Case "ARQUIVO"
                If UBound(partes) >= 1 Then marcaDoArquivo = partes(1)
            Case "PECA"
                If UBound(partes) >= 1 Then pecaDoArquivo = partes(1)
            Case "CONFIGURACAO"
                If UBound(partes) >= 1 Then configuracaoDoArquivo = partes(1)
            Case "CORPO"
                If UBound(partes) >= 12 Then AcrescentarLinha partes
            Case "PERFIL"
                If UBound(partes) >= 3 Then AcrescentarPerfil partes
        End Select
    Loop
    Close #numeroDoArquivo
End Sub

Function DividirLinha(textoDaLinha As String) As Variant
    ' Campos separados por ponto e virgula; entre aspas, o ponto e virgula e as aspas dobradas valem.
    Dim pedacos() As String, n As Long, j As Long, c As String, atual As String, entreAspas As Boolean
    n = 0
    ReDim pedacos(0)
    atual = ""
    entreAspas = False
    j = 1
    Do While j <= Len(textoDaLinha)
        c = Mid(textoDaLinha, j, 1)
        If entreAspas Then
            If c = """" Then
                If Mid(textoDaLinha, j + 1, 1) = """" Then
                    atual = atual & """"
                    j = j + 1
                Else
                    entreAspas = False
                End If
            Else
                atual = atual & c
            End If
        ElseIf c = """" Then
            entreAspas = True
        ElseIf c = ";" Then
            ReDim Preserve pedacos(n)
            pedacos(n) = atual
            n = n + 1
            atual = ""
        Else
            atual = atual & c
        End If
        j = j + 1
    Loop
    ReDim Preserve pedacos(n)
    pedacos(n) = atual
    DividirLinha = pedacos
End Function

Sub AcrescentarLinha(partes As Variant)
    ' CORPO;ATUAL;NOVO;PAPEL;FORMA;X1;Y1;Z1;X2;Y2;Z2;COMPRIMENTO;VOLUME (mm e cm3, ponto decimal).
    Dim n As Long, j As Long
    n = totalLinhas
    ReDim Preserve atuais(n)
    ReDim Preserve novos(n)
    ReDim Preserve restos(n)
    ReDim Preserve pontas(6 * n + 5)
    ReDim Preserve volumes(n)
    atuais(n) = partes(1)
    novos(n) = Trim(partes(2))
    restos(n) = partes(3)
    For j = 4 To 12
        restos(n) = restos(n) & ";" & partes(j)
    Next j
    For j = 0 To 5
        pontas(6 * n + j) = Val(partes(5 + j)) / 1000#
    Next j
    If Trim(partes(12)) = "" Then
        volumes(n) = -1#
    Else
        volumes(n) = Val(partes(12)) / 1000000#
    End If
    totalLinhas = n + 1
End Sub

Sub AcrescentarPerfil(partes As Variant)
    ' PERFIL;ITEM;PERFIL;CORPO DO ITEM (o perfil vazio apaga a propriedade).
    Dim n As Long
    n = totalPerfis
    ReDim Preserve itensDoPerfil(n)
    ReDim Preserve valoresDoPerfil(n)
    ReDim Preserve corposDoPerfil(n)
    ReDim Preserve situacoesDoPerfil(n)
    ReDim Preserve motivosDoPerfil(n)
    ReDim Preserve perfisAntigos(n)
    itensDoPerfil(n) = partes(1)
    valoresDoPerfil(n) = Trim(partes(2))
    corposDoPerfil(n) = partes(3)
    totalPerfis = n + 1
End Sub

Function Massa(swCorpo As SldWorks.Body2) As Variant
    ' Centro de massa (0 a 2) e volume (3, m3) do corpo; Empty se a API falhar.
    On Error Resume Next
    Massa = Empty
    Massa = swCorpo.GetMassProperties(DENSIDADE_ACO)
End Function

Function Confere(ByVal k As Long, ByVal i As Long) As Boolean
    ' O corpo k e o da linha i? O centro de massa na linha de centro do esqueleto e o mesmo volume.
    Confere = False
    If volumesDosCorpos(k) < 0 Then Exit Function
    If DistanciaAoSegmento(centros(3 * k), centros(3 * k + 1), centros(3 * k + 2), i) > TOLERANCIA_DO_CENTRO Then Exit Function
    If volumes(i) > 0 Then
        If Abs(volumesDosCorpos(k) - volumes(i)) > TOLERANCIA_DO_VOLUME * volumes(i) + 0.000001 Then Exit Function
    End If
    Confere = True
End Function

Function DistanciaAoSegmento(ByVal px As Double, ByVal py As Double, ByVal pz As Double, ByVal i As Long) As Double
    Dim ax As Double, ay As Double, az As Double, dx As Double, dy As Double, dz As Double
    Dim t As Double, l2 As Double, ex As Double, ey As Double, ez As Double
    ax = pontas(6 * i)
    ay = pontas(6 * i + 1)
    az = pontas(6 * i + 2)
    dx = pontas(6 * i + 3) - ax
    dy = pontas(6 * i + 4) - ay
    dz = pontas(6 * i + 5) - az
    l2 = dx * dx + dy * dy + dz * dz
    t = 0#
    If l2 > 0# Then t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / l2
    If t < 0# Then t = 0#
    If t > 1# Then t = 1#
    ex = ax + t * dx - px
    ey = ay + t * dy - py
    ez = az + t * dz - pz
    DistanciaAoSegmento = Sqr(ex * ex + ey * ey + ez * ez)
End Function

Function PelaGeometriaDoCorpo(ByVal i As Long) As Long
    ' O unico corpo livre no lugar da linha i; -1 nenhum, -2 mais de um.
    Dim k As Long, achado As Long, quantos As Long
    achado = -1
    quantos = 0
    For k = 0 To totalCorpos - 1
        If Not usados(k) Then
            If Confere(k, i) Then
                quantos = quantos + 1
                achado = k
            End If
        End If
    Next k
    If quantos = 1 Then
        PelaGeometriaDoCorpo = achado
    ElseIf quantos > 1 Then
        PelaGeometriaDoCorpo = -2
    Else
        PelaGeometriaDoCorpo = -1
    End If
End Function

Function NomeValido(nomeNovo As String) As Boolean
    ' O que o SolidWorks nao aceita num corpo: vazio, longo demais, arroba, quebra de linha. O padrao
    ' do programa (letras, numeros, hifen) ja vem conferido pela pagina; o arquivo para desfazer
    ' devolve os nomes antigos, que podem ter barra, colchetes e acento.
    NomeValido = False
    If Len(nomeNovo) = 0 Or Len(nomeNovo) > TAMANHO_MAXIMO Then Exit Function
    If InStr(nomeNovo, "@") > 0 Or InStr(nomeNovo, vbCr) > 0 Or InStr(nomeNovo, vbLf) > 0 Then Exit Function
    NomeValido = True
End Function

Function NomeProvisorio(ByVal i As Long, porNome As Object) As String
    ' Um nome que nenhum corpo tem (nem os nomes novos, que nao comecam assim).
    Dim tentativa As Long
    Do
        NomeProvisorio = "MTK-PROVISORIO-" & i & "-" & tentativa
        tentativa = tentativa + 1
    Loop While porNome.Exists(NomeProvisorio)
End Function

Function Renomear(swCorpo As SldWorks.Body2, nomeNovo As String) As Boolean
    ' Troca e confere: o SolidWorks pode recusar sem dar erro (nome repetido, caractere proibido).
    On Error GoTo Falhou
    Renomear = False
    swCorpo.Name = nomeNovo
    Renomear = (StrComp(swCorpo.Name, nomeNovo, vbBinaryCompare) = 0)
    Exit Function
Falhou:
    Renomear = False
End Function

Sub JuntarPastas(swModel As SldWorks.ModelDoc2, pastas As Collection, pastaDoCorpo As Object)
    ' As pastas da lista de corte (itens) e, para cada corpo, a pasta dele.
    Dim swFeat As SldWorks.Feature, swSub As SldWorks.Feature, swPasta As SldWorks.BodyFolder
    Dim vCorpos As Variant, k As Long, j As Long, swCorpo As SldWorks.Body2
    Set swFeat = swModel.FirstFeature
    Do While Not swFeat Is Nothing
        If swFeat.GetTypeName2 = "SolidBodyFolder" Then
            Set swPasta = swFeat.GetSpecificFeature2
            swPasta.UpdateCutList
            Set swSub = swFeat.GetFirstSubFeature
            Do While Not swSub Is Nothing
                If swSub.GetTypeName2 = "CutListFolder" Then JuntarPasta pastas, swSub
                Set swSub = swSub.GetNextSubFeature
            Loop
        ElseIf swFeat.GetTypeName2 = "CutListFolder" Then
            JuntarPasta pastas, swFeat
        End If
        Set swFeat = swFeat.GetNextFeature
    Loop
    For k = 1 To pastas.Count
        Set swPasta = pastas(k).GetSpecificFeature2
        vCorpos = swPasta.GetBodies
        If IsArray(vCorpos) Then
            For j = 0 To UBound(vCorpos)
                Set swCorpo = vCorpos(j)
                If Not pastaDoCorpo.Exists(swCorpo.Name) Then pastaDoCorpo.Add swCorpo.Name, k
            Next j
        End If
    Next k
End Sub

Sub JuntarPasta(pastas As Collection, swFeat As SldWorks.Feature)
    Dim k As Long
    For k = 1 To pastas.Count
        If pastas(k).Name = swFeat.Name Then Exit Sub
    Next k
    pastas.Add swFeat
End Sub

Function ValorDoPerfil(ByVal swFeat As SldWorks.Feature) As String
    ' O PERFIL que o item tem hoje (vazio sem a propriedade).
    Dim swProps As SldWorks.CustomPropertyManager, valor As String, resolvido As String
    On Error Resume Next
    ValorDoPerfil = ""
    Set swProps = swFeat.CustomPropertyManager
    swProps.Get4 PROPRIEDADE_DO_PERFIL, False, valor, resolvido
    ValorDoPerfil = valor
End Function

Function GravarPerfil(ByVal swFeat As SldWorks.Feature, valorNovo As String) As Boolean
    ' Grava (ou apaga, com o valor vazio) o PERFIL do item e confere lendo de volta.
    Dim swProps As SldWorks.CustomPropertyManager
    On Error GoTo Falhou
    GravarPerfil = False
    Set swProps = swFeat.CustomPropertyManager
    If valorNovo = "" Then
        swProps.Delete2 PROPRIEDADE_DO_PERFIL
    Else
        swProps.Add3 PROPRIEDADE_DO_PERFIL, TIPO_TEXTO, valorNovo, SUBSTITUIR_VALOR
    End If
    GravarPerfil = (ValorDoPerfil(swFeat) = valorNovo)
    Exit Function
Falhou:
    GravarPerfil = False
End Function

Sub AtualizarArvore(swModel As SldWorks.ModelDoc2)
    ' A arvore mostra os nomes novos e a peca fica marcada para salvar.
    On Error Resume Next
    swModel.FeatureManager.UpdateFeatureTree
    swModel.SetSaveFlag
End Sub

Function NomeDaConfiguracao(swModel As SldWorks.ModelDoc2) As String
    ' So informativo: se a API falhar, sai vazio.
    On Error Resume Next
    NomeDaConfiguracao = ""
    NomeDaConfiguracao = swModel.ConfigurationManager.ActiveConfiguration.Name
End Function

Sub GravarRelatorio(caminhoDoRelatorio As String, peca As String, configuracao As String, _
    quando As String, caminhoLido As String)
    Dim numeroDoArquivo As Integer, i As Long, antigo As String
    numeroDoArquivo = FreeFile
    Open caminhoDoRelatorio For Output As #numeroDoArquivo
    Print #numeroDoArquivo, "RELATORIO;" & Campo("Mecanica Toolkit - renomear_corpos " & VERSAO_DA_MACRO)
    Print #numeroDoArquivo, "PECA;" & Campo(peca)
    Print #numeroDoArquivo, "CONFIGURACAO;" & Campo(configuracao)
    Print #numeroDoArquivo, "DATA;" & Campo(quando)
    Print #numeroDoArquivo, "ARQUIVO LIDO;" & Campo(caminhoLido)
    Print #numeroDoArquivo, "TIPO;ANTIGO;NOVO;SITUACAO;MOTIVO"
    For i = 0 To totalLinhas - 1
        antigo = atuais(i)
        If alvos(i) >= 0 Then antigo = nomesDosCorpos(alvos(i))
        Print #numeroDoArquivo, "CORPO;" & Campo(antigo) & ";" & Campo(novos(i)) & ";" & _
            situacoes(i) & ";" & Campo(motivos(i))
    Next i
    For i = 0 To totalPerfis - 1
        Print #numeroDoArquivo, "PERFIL;" & Campo(itensDoPerfil(i)) & ";" & Campo(valoresDoPerfil(i)) & ";" & _
            situacoesDoPerfil(i) & ";" & Campo("antes: " & perfisAntigos(i) & " " & motivosDoPerfil(i))
    Next i
    Close #numeroDoArquivo
End Sub

Sub GravarDesfazer(caminhoDoArquivo As String, peca As String, configuracao As String, quando As String)
    ' O mesmo formato do arquivo de nomes, ao contrario: rodar a macro com ele volta tudo.
    Dim numeroDoArquivo As Integer, i As Long
    numeroDoArquivo = FreeFile
    Open caminhoDoArquivo For Output As #numeroDoArquivo
    Print #numeroDoArquivo, "ARQUIVO;" & Campo("Mecanica Toolkit - nomes das barras (desfazer) " & VERSAO_DA_MACRO)
    Print #numeroDoArquivo, "PECA;" & Campo(peca)
    Print #numeroDoArquivo, "CONFIGURACAO;" & Campo(configuracao)
    Print #numeroDoArquivo, "ESQUELETO;" & Campo("")
    Print #numeroDoArquivo, "DATA;" & Campo(quando)
    Print #numeroDoArquivo, "CORPOS;ATUAL;NOVO;PAPEL;FORMA;X1 (mm);Y1 (mm);Z1 (mm);X2 (mm);Y2 (mm);Z2 (mm);COMPRIMENTO (mm);VOLUME (cm3)"
    For i = 0 To totalLinhas - 1
        If Left(situacoes(i), 9) = "RENOMEADO" Then
            Print #numeroDoArquivo, "CORPO;" & Campo(novos(i)) & ";" & Campo(nomesDosCorpos(alvos(i))) & ";" & restos(i)
        End If
    Next i
    Print #numeroDoArquivo, "PERFIS;ITEM;PERFIL;CORPO DO ITEM"
    For i = 0 To totalPerfis - 1
        If situacoesDoPerfil(i) = "GRAVADO" Or situacoesDoPerfil(i) = "APAGADO" Then
            Print #numeroDoArquivo, "PERFIL;" & Campo(itensDoPerfil(i)) & ";" & Campo(perfisAntigos(i)) & ";" & _
                Campo(NomeDepois(corposDoPerfil(i)))
        End If
    Next i
    Close #numeroDoArquivo
End Sub

Function NomeDepois(nomeAntes As String) As String
    ' O nome que o corpo tem depois da troca (o mesmo, se ele nao trocou).
    Dim i As Long
    NomeDepois = nomeAntes
    For i = 0 To totalLinhas - 1
        If alvos(i) >= 0 And Left(situacoes(i), 9) = "RENOMEADO" Then
            If StrComp(nomesDosCorpos(alvos(i)), nomeAntes, vbTextCompare) = 0 Then NomeDepois = novos(i)
        End If
    Next i
End Function

Function Campo(texto As String) As String
    Dim t As String
    t = Replace(Replace(texto, vbCr, " "), vbLf, " ")
    Campo = """" & Replace(t, """", """""") & """"
End Function
