import 'dart:math' as math;

import 'package:app/core/theme/app_theme.dart';
import 'package:app/core/theme/cores.dart';
import 'package:app/core/theme/tokens.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:app/features/resposta/presentation/widgets/balao_pergunta.dart';
import 'package:app/features/resposta/presentation/widgets/cartao_alerta.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Razão de contraste WCAG entre duas cores opacas.
double contraste(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05);
}

ThemeData _tema(CoresVetFarmaco c, Brightness b) =>
    ThemeData(brightness: b, scaffoldBackgroundColor: c.paper, extensions: [c]);

void main() {
  group('contraste WCAG AA, nos dois temas', () {
    final temas = {
      'claro': CoresVetFarmaco.claro,
      'escuro': CoresVetFarmaco.escuro,
    };
    for (final MapEntry(key: nome, value: c) in temas.entries) {
      test('texto sobre o fundo e sobre superfícies ≥ 4,5:1 ($nome)', () {
        expect(contraste(c.ink, c.paper), greaterThanOrEqualTo(4.5));
        expect(contraste(c.ink, c.surface), greaterThanOrEqualTo(4.5));
        expect(contraste(c.inkMuted, c.paper), greaterThanOrEqualTo(4.5));
        expect(contraste(c.inkMuted, c.surface), greaterThanOrEqualTo(4.5));
      });

      test('cores de ação, evidência e risco como texto ≥ 4,5:1 ($nome)', () {
        for (final cor in [c.metileno, c.ancorado, c.iodo, c.contra]) {
          expect(contraste(cor, c.paper), greaterThanOrEqualTo(4.5));
          expect(contraste(cor, c.surface), greaterThanOrEqualTo(4.5));
        }
      });

      test('texto sobre o botão primário ≥ 4,5:1 ($nome)', () {
        expect(
          contraste(c.sobreMetileno, c.metileno),
          greaterThanOrEqualTo(4.5),
        );
      });
    }

    test('blocos de alerta sólidos com texto branco ≥ 4,5:1 (fixos)', () {
      expect(contraste(Colors.white, Tokens.iodo), greaterThanOrEqualTo(4.5));
      expect(contraste(Colors.white, Tokens.contra), greaterThanOrEqualTo(4.5));
    });

    test('trilho e bordas de campo ≥ 3:1 no escuro', () {
      const c = CoresVetFarmaco.escuro;
      for (final cor in [c.ancorado, c.iodo, c.contra]) {
        expect(contraste(cor, c.paper), greaterThanOrEqualTo(3));
      }
      expect(
        contraste(const Color(0xFF6F7E78), c.paper),
        greaterThanOrEqualTo(3),
      );
    });
  });

  group('cartão de alerta: contraste nos dois temas', () {
    final temas = {
      'claro': CoresVetFarmaco.claro,
      'escuro': CoresVetFarmaco.escuro,
    };
    for (final MapEntry(key: nome, value: c) in temas.entries) {
      for (final sev in SeveridadeAlerta.values) {
        test('texto, barra e chip sobre o fundo tingido ($nome, $sev)', () {
          final fundo = fundoAlerta(c, sev);
          // Título, palavra da severidade e corpo usam ink: ≥ 4,5:1.
          expect(contraste(c.ink, fundo), greaterThanOrEqualTo(4.5));
          // Barra e ícone: elementos gráficos, ≥ 3:1.
          expect(
            contraste(destaqueAlerta(c, sev), fundo),
            greaterThanOrEqualTo(3),
          );
          // Número do chip (ancorado sobre a própria tinta, sobre o cartão).
          final chip = Color.alphaBlend(
            c.ancorado.withValues(alpha: 0.10),
            fundo,
          );
          expect(contraste(c.ancorado, chip), greaterThanOrEqualTo(4.5));
          // Rótulo «Fonte:» em inkMuted.
          expect(contraste(c.inkMuted, fundo), greaterThanOrEqualTo(4.5));
          // A barra compacta usa o mesmo fundo e a mesma tinta.
          expect(contraste(c.ink, fundo), greaterThanOrEqualTo(4.5));
        });
      }
    }

    test('o fundo é tingido: nunca o vermelho nem o âmbar sólidos', () {
      for (final c in temas.values) {
        for (final sev in SeveridadeAlerta.values) {
          expect(fundoAlerta(c, sev), isNot(destaqueAlerta(c, sev)));
          expect(fundoAlerta(c, sev), isNot(const Color(0xFFFF0000)));
          // Mais perto do fundo da tela do que da cor de destaque.
          final fundo = fundoAlerta(c, sev).computeLuminance();
          expect(
            (fundo - c.paper.computeLuminance()).abs(),
            lessThan((fundo - destaqueAlerta(c, sev).computeLuminance()).abs()),
          );
        }
      }
    });
  });

  group('temas', () {
    test('claro e escuro carregam as próprias cores e o brilho', () {
      expect(appTheme.brightness, Brightness.light);
      expect(temaEscuro.brightness, Brightness.dark);
      expect(appTheme.extension<CoresVetFarmaco>(), CoresVetFarmaco.claro);
      expect(temaEscuro.extension<CoresVetFarmaco>(), CoresVetFarmaco.escuro);
      expect(appTheme.scaffoldBackgroundColor, Tokens.paper);
      expect(temaEscuro.scaffoldBackgroundColor, CoresVetFarmaco.escuro.paper);
    });

    test('texto principal e botão primário seguem o tema', () {
      expect(temaEscuro.textTheme.bodyLarge?.color, CoresVetFarmaco.escuro.ink);
      expect(
        temaEscuro.textTheme.bodySmall?.color,
        CoresVetFarmaco.escuro.inkMuted,
      );
      expect(temaEscuro.colorScheme.primary, CoresVetFarmaco.escuro.metileno);
      expect(
        temaEscuro.colorScheme.onPrimary,
        CoresVetFarmaco.escuro.sobreMetileno,
      );
      expect(appTheme.colorScheme.primary, Tokens.metileno);
    });

    test('sem a extensão o contexto usa o tema claro', () {
      expect(CoresVetFarmaco.claro.ink, Tokens.ink);
    });
  });

  group('componentes no tema escuro', () {
    const e = CoresVetFarmaco.escuro;
    Widget app(Widget filho) => MaterialApp(
      theme: _tema(CoresVetFarmaco.claro, Brightness.light),
      darkTheme: _tema(e, Brightness.dark),
      themeMode: ThemeMode.dark,
      home: Scaffold(body: filho),
    );

    testWidgets('chip de citação usa o verde claro', (tester) async {
      await tester.pumpWidget(
        app(
          const AncoraCitacao(
            citacao: Citacao(chunkId: 'c', indice: 3, trecho: 't', fonte: 'f'),
          ),
        ),
      );
      final numero = tester.widget<Text>(find.text('3'));
      expect(numero.style?.color, e.ancorado);
    });

    testWidgets('balão da pergunta usa o azul claro com texto escuro', (
      tester,
    ) async {
      await tester.pumpWidget(
        app(
          const BalaoPergunta(
            corpo: CorpoConsulta(
              pergunta: 'Pode?',
              complexidadeDica: 'baixa',
              especie: 'felino',
            ),
          ),
        ),
      );
      final texto = tester.widget<Text>(find.text('Pode?'));
      expect(texto.style?.color, e.sobreMetileno);
      final caixa = tester.widget<Container>(
        find
            .ancestor(of: find.text('Pode?'), matching: find.byType(Container))
            .first,
      );
      expect((caixa.decoration! as BoxDecoration).color, e.metileno);
    });

    testWidgets('cartão de alerta usa tinta do tema escuro, sem cor sólida', (
      tester,
    ) async {
      await tester.pumpWidget(
        app(
          const CartaoAlerta(
            itens: [
              ItemAlerta(
                severidade: SeveridadeAlerta.contraindicacao,
                texto: 'Texto do alerta.',
              ),
            ],
          ),
        ),
      );
      final titulo = tester.widget<Text>(find.text('Alerta de segurança'));
      expect(titulo.style?.color, e.ink);
      final caixa = tester.widget<DecoratedBox>(
        find
            .descendant(
              of: find.byType(ClipRRect),
              matching: find.byType(DecoratedBox),
            )
            .first,
      );
      expect(
        (caixa.decoration as BoxDecoration).color,
        fundoAlerta(e, SeveridadeAlerta.contraindicacao),
      );
      expect(
        fundoAlerta(e, SeveridadeAlerta.contraindicacao),
        isNot(e.contra),
        reason: 'fundo tingido, não vermelho sólido',
      );
    });
  });
}
