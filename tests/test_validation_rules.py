"""Testes das regras plugáveis da Central de Validação.

As regras são o ponto de extensão de que a arquitetura depende para crescer,
e até agora não tinham teste próprio. O foco aqui são as regras que olham
**resultado de engenharia**: um projeto pode chegar à emissão completo,
assinado e coerente, e ainda assim carregar um cálculo que não passa.
"""

import unittest

from core.validation_plugins import (
    RegraValidacao,
    executar_regras,
    listar_regras,
    registrar_regra,
)


def projeto_com(*registros, criterios=None) -> dict:
    projeto = {"registros_tecnicos": list(registros)}
    if criterios is not None:
        projeto["criterios_projeto"] = criterios
    return projeto


def registro(
    *,
    titulo="Verificação",
    modulo="Vigas e eixos",
    status="Atende",
    resultados=None,
) -> dict:
    return {
        "titulo": titulo,
        "modulo": modulo,
        "modulo_id": "vigas_eixos",
        "status": status,
        "entradas": {},
        "resultados": resultados or {},
    }


def achados_da_regra(projeto, regra_id: str) -> list:
    for regra, resultado in executar_regras(projeto):
        if regra.id == regra_id:
            return list(resultado.achados)
    raise AssertionError(f"Regra {regra_id!r} não está registrada.")


class RegistroDeRegrasTests(unittest.TestCase):
    def test_regras_padrao_estao_registradas(self):
        ids = {regra.id for regra in listar_regras()}
        self.assertIn("contrato-registro", ids)
        self.assertIn("margens-calculadas", ids)
        self.assertIn("deslocamentos", ids)

    def test_registro_duplicado_e_recusado(self):
        with self.assertRaises(ValueError):
            registrar_regra(
                RegraValidacao("margens-calculadas", "Duplicada", "1.0", lambda _: None)
            )

    def test_projeto_vazio_nao_gera_achado_de_margem(self):
        self.assertEqual(achados_da_regra(projeto_com(), "margens-calculadas"), [])


class MargensCalculadasTests(unittest.TestCase):
    def test_fator_abaixo_de_um_e_bloqueio(self):
        achados = achados_da_regra(
            projeto_com(registro(resultados={"fator_seguranca_escoamento": 0.85})),
            "margens-calculadas",
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Bloqueio")
        self.assertIn("0.85", achados[0].detalhe)

    def test_fator_entre_um_e_a_meta_e_atencao(self):
        achados = achados_da_regra(
            projeto_com(registro(resultados={"fator_seguranca_escoamento": 1.2})),
            "margens-calculadas",
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Atenção")

    def test_fator_acima_da_meta_nao_gera_achado(self):
        self.assertEqual(
            achados_da_regra(
                projeto_com(registro(resultados={"fator_seguranca_escoamento": 2.4})),
                "margens-calculadas",
            ),
            [],
        )

    def test_meta_gravada_no_registro_prevalece(self):
        # 1,2 passa quando o cálculo foi feito com meta 1,1 — é a meta que
        # valia na época, e é a que o memorial reproduz.
        self.assertEqual(
            achados_da_regra(
                projeto_com(
                    registro(
                        resultados={
                            "fator_seguranca_escoamento": 1.2,
                            "fator_seguranca_minimo": 1.1,
                        }
                    )
                ),
                "margens-calculadas",
            ),
            [],
        )

    def test_meta_do_projeto_e_respeitada(self):
        criterios = {"seguranca": {"fator_seguranca_minimo": 3.0}}
        achados = achados_da_regra(
            projeto_com(
                registro(resultados={"fator_seguranca_escoamento": 2.4}),
                criterios=criterios,
            ),
            "margens-calculadas",
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Atenção")
        self.assertIn("3.00", achados[0].detalhe)

    def test_menor_fator_governa_quando_ha_varios(self):
        achados = achados_da_regra(
            projeto_com(
                registro(
                    resultados={
                        "fator_seguranca": 3.0,
                        "fator_ruptura": 0.7,
                    }
                )
            ),
            "margens-calculadas",
        )
        self.assertEqual(achados[0].severidade, "Bloqueio")
        self.assertIn("fator_ruptura", achados[0].evidencia)

    def test_utilizacao_acima_do_limite_e_bloqueio(self):
        achados = achados_da_regra(
            projeto_com(registro(resultados={"utilizacao": 1.3})),
            "margens-calculadas",
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Bloqueio")
        self.assertIn("130%", achados[0].detalhe)

    def test_status_nao_atende_e_bloqueio(self):
        achados = achados_da_regra(
            projeto_com(registro(status="Não atende")), "margens-calculadas"
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Bloqueio")

    def test_status_atencao_gera_ressalva(self):
        achados = achados_da_regra(
            projeto_com(registro(status="Atenção")), "margens-calculadas"
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Atenção")

    def test_valores_nao_numericos_sao_ignorados(self):
        # Registros antigos ou incompletos não podem derrubar a validação.
        self.assertEqual(
            achados_da_regra(
                projeto_com(
                    registro(
                        resultados={
                            "fator_seguranca": None,
                            "utilizacao": "n/d",
                        }
                    )
                ),
                "margens-calculadas",
            ),
            [],
        )

    def test_contagem_de_pontos_reflete_os_calculos_avaliados(self):
        projeto = projeto_com(
            registro(titulo="A", resultados={"fator_seguranca": 3.0}),
            registro(titulo="B", resultados={"fator_seguranca": 2.0}),
            registro(titulo="C", resultados={"fator_seguranca": 0.5}),
        )
        for regra, resultado in executar_regras(projeto):
            if regra.id == "margens-calculadas":
                self.assertEqual(resultado.pontos_totais, 3)
                self.assertEqual(resultado.pontos_preenchidos, 2)
                return
        self.fail("regra não executada")


class DeslocamentosTests(unittest.TestCase):
    def test_flecha_acima_do_admissivel_gera_atencao(self):
        achados = achados_da_regra(
            projeto_com(
                registro(
                    resultados={
                        "flecha_maxima_mm": -37.2,
                        "flecha_admissivel_mm": 17.1,
                        "criterio_flecha": "L/350",
                    }
                )
            ),
            "deslocamentos",
        )
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].severidade, "Atenção")
        self.assertIn("L/350", achados[0].detalhe)

    def test_o_sinal_da_flecha_nao_importa(self):
        # Flecha para baixo é negativa; o critério compara magnitudes.
        para_baixo = achados_da_regra(
            projeto_com(
                registro(
                    resultados={"flecha_maxima_mm": -20.0, "flecha_admissivel_mm": 10.0}
                )
            ),
            "deslocamentos",
        )
        para_cima = achados_da_regra(
            projeto_com(
                registro(
                    resultados={"flecha_maxima_mm": 20.0, "flecha_admissivel_mm": 10.0}
                )
            ),
            "deslocamentos",
        )
        self.assertEqual(len(para_baixo), len(para_cima), 1)

    def test_flecha_dentro_do_criterio_nao_gera_achado(self):
        self.assertEqual(
            achados_da_regra(
                projeto_com(
                    registro(
                        resultados={"flecha_maxima_mm": -8.0, "flecha_admissivel_mm": 17.1}
                    )
                ),
                "deslocamentos",
            ),
            [],
        )

    def test_registro_sem_criterio_e_ignorado(self):
        self.assertEqual(
            achados_da_regra(
                projeto_com(registro(resultados={"flecha_maxima_mm": -37.2})),
                "deslocamentos",
            ),
            [],
        )


class IntegracaoComVigaRealTests(unittest.TestCase):
    def test_viga_reprovada_em_tensao_e_flecha_aparece_nas_duas_regras(self):
        from core import beam_analysis as vb
        from core import beam_script as bs

        # Viga deliberadamente subdimensionada: 8 m de vão numa barra de 50 mm.
        resultado = vb.analisar_viga(
            bs.interpretar(
                """
                viga 8
                secao circular 50
                material aco
                apoio 0 pino
                apoio 8 rolete
                q 0 8 5 baixo
                """
            )
        )
        verificacao = vb.verificar_flecha(resultado)
        self.assertLess(resultado.fator_seguranca_escoamento, 1.0)
        self.assertFalse(verificacao["atende"])

        projeto = projeto_com(
            registro(
                titulo="Viga subdimensionada",
                status="Não atende",
                resultados={
                    "fator_seguranca_escoamento": resultado.fator_seguranca_escoamento,
                    "fator_seguranca_minimo": 1.5,
                    "flecha_maxima_mm": resultado.extremos["flecha"].valor,
                    "flecha_admissivel_mm": verificacao["flecha_admissivel_mm"],
                    "criterio_flecha": verificacao["criterio"],
                },
            )
        )
        margens = achados_da_regra(projeto, "margens-calculadas")
        deslocamentos = achados_da_regra(projeto, "deslocamentos")
        self.assertTrue(any(a.severidade == "Bloqueio" for a in margens))
        self.assertEqual(len(deslocamentos), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
