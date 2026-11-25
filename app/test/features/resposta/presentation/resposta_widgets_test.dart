import 'dart:async';

import 'package:app/core/error/failures.dart';
import 'package:app/core/theme/cores.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/dose.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/resposta/presentation/pages/resposta_page.dart';
import 'package:app/features/resposta/presentation/texto_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:app/features/resposta/presentation/widgets/balao_pergunta.dart';
import 'package:app/features/resposta/presentation/widgets/cartao_alerta.dart';
import 'package:app/features/resposta/presentation/widgets/espera_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/trilho_evidencia.dart';
import 'package:app/shared/widgets/brilho.dart';
import 'package:app/shared/widgets/icone_vetfarmaco.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

const _corpo = CorpoConsulta(
  pergunta: 'Pode?',
  complexidadeDica: 'baixa',
  especie: 'felino',
  pesoKg: 4.2,
  farmacos: ['meloxicam'],
);

const _c1 = Citacao(
  chunkId: 'c1',
  indice: 1,
  trecho: 'O uso repetido de meloxicam em gatos...',
  fonte: 'Spinosa et al. (2017)',
  capitulo: '22',
);
const _c2 = Citacao(
  chunkId: 'c2',
  indice: 2,
  trecho: 'Bula.',
  fonte: 'Bula — meloxicam',
  pagina: 3,
);
const _p0 = EventoParagrafo(
  indice: 1,
  texto: 'Meloxicam é um AINE.',
  chunkIds: ['c1', 'c2'],
);
const _fim = EventoFim(
  nivelConfianca: NivelConfianca.alta,
  modelo: 'm-1',
  tempos: TemposServidor(primeiroParagrafoValidado: 1400, total: 5200),
);

void main() {
  group('contemDose', () {
    test('reconhece valores de dose', () {
      for (final t in [
        'Dar 0,1 mg/kg a cada 24 h.',
        'Usar 5mg por via oral',
        '2 mL de solução',
        '10 UI',
        '1,5 g/dia',
      ]) {
        expect(contemDose(t), isTrue, reason: t);
      }
    });

    test('não confunde peso nem palavras', () {
      for (final t in [
        'Gato de 4,2 kg.',
        'O meloxicam é um AINE.',
        '5 gatos foram tratados.',
        'Em 12 meses.',
      ]) {
        expect(contemDose(t), isFalse, reason: t);
      }
    });
  });

  group('texto_resposta', () {
    test('resumo, citações do parágrafo e rodapé', () {
      expect(resumoConsulta(_corpo), 'Meloxicam · felino · 4,2 kg');
      expect(
        resumoConsulta(
          const CorpoConsulta(pergunta: 'x', complexidadeDica: 'baixa'),
        ),
        'Resposta',
      );
      expect(citacoesDoParagrafo(_p0, [_c2, _c1]), [_c1, _c2]);
      expect(citacoesDoParagrafo(_p0, []), isEmpty);
      expect(
        rodapeResposta(fim: _fim, geradaEm: DateTime(2026, 3, 12, 9, 5)),
        'Confiança alta · m-1 · 12/03/2026 09:05 · '
        '1,4 s até o primeiro parágrafo · 5,2 s total',
      );
    });

    test('o texto copiado inclui as citações', () {
      final texto = textoParaCopiar(
        RespostaState(
          fase: FaseResposta.concluida,
          paragrafos: const [_p0],
          citacoes: const [_c1, _c2],
          alerta: const EventoAlerta(
            severidade: SeveridadeAlerta.cautela,
            texto: 'Risco renal.',
            chunkIds: ['c1'],
          ),
          fim: _fim,
          geradaEm: DateTime(2026, 3, 12),
        ),
      );
      expect(texto, startsWith('CAUTELA: Risco renal.'));
      expect(texto, contains('Meloxicam é um AINE. [1][2]'));
      expect(texto, contains('[1] "O uso repetido de meloxicam em gatos..."'));
      expect(texto, contains('Spinosa et al. (2017), capítulo 22'));
      expect(texto, contains('Bula — meloxicam, página 3'));
      expect(texto, contains('Confiança alta · m-1'));
    });
  });

  group('widgets', () {
    testWidgets('âncora tem alvo de 48 dp, semântica e dispara o toque', (
      tester,
    ) async {
      Citacao? tocada;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AncoraCitacao(citacao: _c1, aoTocar: (c) => tocada = c),
          ),
        ),
      );
      final tamanho = tester.getSize(find.byType(AncoraCitacao));
      expect(tamanho.width, greaterThanOrEqualTo(48));
      expect(tamanho.height, greaterThanOrEqualTo(48));
      expect(
        find.bySemanticsLabel(
          'citação 1, Spinosa et al. (2017), capítulo 22, abrir trecho',
        ),
        findsOneWidget,
      );
      await tester.tap(find.byType(AncoraCitacao));
      expect(tocada, _c1);
    });

    testWidgets('cartão de alerta: título, palavra da severidade e texto', (
      tester,
    ) async {
      for (final (sev, palavra) in [
        (SeveridadeAlerta.contraindicacao, 'Contraindicação'),
        (SeveridadeAlerta.cautela, 'Cautela'),
      ]) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: CartaoAlerta(
                itens: [ItemAlerta(severidade: sev, texto: 'Texto literal.')],
              ),
            ),
          ),
        );
        expect(find.text('Alerta de segurança'), findsOneWidget);
        expect(find.text(palavra), findsOneWidget);
        expect(find.text('Texto literal.'), findsOneWidget);
        // Sem maiúsculas gritando, sem exclamação.
        expect(find.text(palavra.toUpperCase()), findsNothing);
        expect(find.textContaining('!'), findsNothing);
      }
    });

    testWidgets('cartão: sem sombra, barra de 4 dp e raio dos cartões', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.contraindicacao,
                  texto: 'Texto.',
                ),
              ],
            ),
          ),
        ),
      );
      final clip = tester.widget<ClipRRect>(find.byType(ClipRRect));
      expect(clip.borderRadius, BorderRadius.circular(raioCartao));
      expect(raioCartao, 12);
      final decoracao = tester.widget<DecoratedBox>(
        find
            .descendant(
              of: find.byType(ClipRRect),
              matching: find.byType(DecoratedBox),
            )
            .first,
      );
      expect((decoracao.decoration as BoxDecoration).boxShadow, isNull);
      final barra = tester.widget<Container>(
        find
            .descendant(
              of: find.byType(ClipRRect),
              matching: find.byWidgetPredicate(
                (w) => w is Container && w.constraints?.maxWidth == 4,
              ),
            )
            .first,
      );
      expect(barra.constraints?.maxWidth, 4);
    });

    testWidgets('vários alertas: um cabeçalho, itens com a própria gravidade', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Primeiro alerta.',
                ),
                ItemAlerta(
                  severidade: SeveridadeAlerta.contraindicacao,
                  texto: 'Segundo alerta.',
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.byType(CartaoAlerta), findsOneWidget);
      expect(find.byType(ClipRRect), findsOneWidget);
      expect(find.byType(Divider), findsOneWidget);
      // Cabeçalho uma vez, com a contagem.
      expect(find.text('2 alertas de segurança'), findsOneWidget);
      expect(find.text('Alerta de segurança'), findsNothing);
      // Cada item só com o rótulo da gravidade, o ícone dela e o texto.
      expect(find.text('Cautela'), findsOneWidget);
      expect(find.text('Contraindicação'), findsOneWidget);
      expect(find.text('Primeiro alerta.'), findsOneWidget);
      expect(find.text('Segundo alerta.'), findsOneWidget);
      // Ícone do cabeçalho segue a gravidade mais alta (contraindicação).
      expect(find.byIcon(Icons.error_outline), findsNWidgets(2));
      expect(find.byIcon(Icons.warning_amber_outlined), findsOneWidget);
    });

    testWidgets('itens por gravidade: contraindicação primeiro', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Cautela A.',
                ),
                ItemAlerta(
                  severidade: SeveridadeAlerta.contraindicacao,
                  texto: 'Contra A.',
                ),
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Cautela B.',
                ),
                ItemAlerta(
                  severidade: SeveridadeAlerta.contraindicacao,
                  texto: 'Contra B.',
                ),
              ],
            ),
          ),
        ),
      );
      final ordem = [
        for (final t in ['Contra A.', 'Contra B.', 'Cautela A.', 'Cautela B.'])
          tester.getTopLeft(find.text(t)).dy,
      ];
      // Contraindicações antes das cautelas, cada grupo na ordem de chegada.
      expect(ordem, orderedEquals([...ordem]..sort()));
      expect(find.text('4 alertas de segurança'), findsOneWidget);
    });

    test('itensPorGravidade é estável dentro da mesma gravidade', () {
      const a = ItemAlerta(severidade: SeveridadeAlerta.cautela, texto: 'a');
      const b = ItemAlerta(
        severidade: SeveridadeAlerta.contraindicacao,
        texto: 'b',
      );
      const c = ItemAlerta(severidade: SeveridadeAlerta.cautela, texto: 'c');
      expect(itensPorGravidade([a, b, c]).map((i) => i.texto), ['b', 'a', 'c']);
      expect(itensPorGravidade(const []), isEmpty);
    });

    testWidgets('um alerta: título no singular e rótulo sem ícone', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Texto.',
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Alerta de segurança'), findsOneWidget);
      // Com um alerta só, o ícone fica no cabeçalho; a linha da gravidade
      // tem só o rótulo.
      expect(find.text('Cautela'), findsOneWidget);
      expect(find.byIcon(Icons.warning_amber_outlined), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsNothing);
    });

    testWidgets('«Fonte:» fica no fim de cada item, com chips menores', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.contraindicacao,
                  texto: 'Primeiro alerta.',
                  fontes: [_c1],
                ),
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Segundo alerta.',
                  fontes: [_c1, _c2],
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Fonte:'), findsNWidgets(2));
      expect(find.byType(AncoraCitacao), findsNWidgets(3));
      // Fora do cabeçalho: cada «Fonte:» vem depois do texto do seu item.
      final fontes = find.text('Fonte:').evaluate().length;
      expect(fontes, 2);
      expect(
        tester.getTopLeft(find.text('Fonte:').first).dy,
        greaterThan(tester.getBottomLeft(find.text('Primeiro alerta.')).dy - 1),
      );
      expect(
        tester.getTopLeft(find.text('Fonte:').last).dy,
        greaterThan(tester.getBottomLeft(find.text('Segundo alerta.')).dy - 1),
      );
      // Visual menor (22 dp), área de toque de 48 dp.
      final chip = find.byType(AncoraCitacao).first;
      expect(tester.getSize(chip).height, greaterThanOrEqualTo(48));
      expect(tester.getSize(chip).width, greaterThanOrEqualTo(48));
      final visual = tester.getSize(
        find.descendant(of: chip, matching: find.byType(Container)).first,
      );
      expect(visual.height, 22);
    });

    testWidgets('sem fontes carregadas não há linha «Fonte:»', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Texto.',
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Fonte:'), findsNothing);
    });

    testWidgets('barra compacta: raio de 12 dp e cor da gravidade mais alta', (
      tester,
    ) async {
      for (final sev in SeveridadeAlerta.values) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BarraAlertaCompacta(
                quantidade: 2,
                severidade: sev,
                aoTocar: () {},
              ),
            ),
          ),
        );
        final clip = tester.widget<ClipRRect>(find.byType(ClipRRect));
        expect(clip.borderRadius, BorderRadius.circular(raioCartao));
        final material = tester.widget<Material>(
          find.descendant(
            of: find.byType(BarraAlertaCompacta),
            matching: find.byType(Material),
          ),
        );
        expect(material.color, fundoAlerta(CoresVetFarmaco.claro, sev));
        expect(find.byIcon(iconeSeveridade(sev)), findsOneWidget);
      }
    });

    testWidgets('texto longo aparece inteiro e quebra linha em fonte 2.0', (
      tester,
    ) async {
      final longo = List.filled(40, 'doses repetidas em gatos').join(', ');
      tester.view
        ..physicalSize = const Size(380, 1600)
        ..devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: CartaoAlerta(
                itens: [
                  ItemAlerta(
                    severidade: SeveridadeAlerta.contraindicacao,
                    texto: longo,
                    fontes: const [_c1, _c2],
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.text(longo), findsOneWidget);
      final texto = tester.widget<SelectableText>(
        find.widgetWithText(SelectableText, longo),
      );
      expect(texto.maxLines, isNull);
      // 40 repetições a 2× em 380 px ocupam muitas linhas, sem corte.
      expect(
        tester.getSize(find.widgetWithText(SelectableText, longo)).height,
        greaterThan(300),
      );
    });

    testWidgets('chips da fonte abrem o trecho e têm alvo de 48 dp', (
      tester,
    ) async {
      Citacao? aberta;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: const [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Texto.',
                  fontes: [_c1, _c2],
                ),
              ],
              aoAbrirCitacao: (c) => aberta = c,
            ),
          ),
        ),
      );
      expect(find.byType(AncoraCitacao), findsNWidgets(2));
      for (final chip in tester.widgetList(find.byType(AncoraCitacao))) {
        expect(chip, isA<AncoraCitacao>());
      }
      final alvo = tester.getSize(find.byType(AncoraCitacao).first);
      expect(alvo.width, greaterThanOrEqualTo(48));
      expect(alvo.height, greaterThanOrEqualTo(48));
      await tester.tap(find.byType(AncoraCitacao).last);
      expect(aberta, _c2);
    });

    testWidgets('sem citações carregadas, o cartão não mostra chips', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CartaoAlerta(
              itens: [
                ItemAlerta(
                  severidade: SeveridadeAlerta.cautela,
                  texto: 'Texto.',
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.byType(AncoraCitacao), findsNothing);
    });

    testWidgets('barra compacta: texto, plural e alvo de 48 dp', (
      tester,
    ) async {
      var toques = 0;
      for (final (n, texto) in [
        (1, '1 alerta de segurança · ver'),
        (2, '2 alertas de segurança · ver'),
      ]) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: BarraAlertaCompacta(
                quantidade: n,
                severidade: SeveridadeAlerta.cautela,
                aoTocar: () => toques++,
              ),
            ),
          ),
        );
        expect(find.text(texto), findsOneWidget);
        expect(
          tester.getSize(find.byType(BarraAlertaCompacta)).height,
          greaterThanOrEqualTo(48),
        );
      }
      await tester.tap(find.byType(BarraAlertaCompacta));
      expect(toques, 1);
    });

    testWidgets('trilho renderiza os três tipos em torno do conteúdo', (
      tester,
    ) async {
      for (final tipo in TipoTrilho.values) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TrilhoEvidencia(tipo: tipo, child: const Text('x')),
            ),
          ),
        );
        expect(find.text('x'), findsOneWidget);
        expect(tester.getSize(find.byType(CustomPaint).last).width, 3);
      }
    });
  });

  group('RespostaPage (4.7)', () {
    late _MockRealizar realizar;
    late StreamController<Either<Failure, EventoResposta>> ctl;
    late RespostaCubit cubit;

    setUp(() {
      realizar = _MockRealizar();
      ctl = StreamController();
      when(() => realizar(_corpo)).thenAnswer((_) => ctl.stream);
      cubit = novoRespostaCubit(realizar);
    });

    tearDown(() async {
      await cubit.close();
      await ctl.close();
    });

    Future<void> abrir(
      WidgetTester tester, {
      ValueChanged<Citacao>? aoAbrir,
      double escala = 1,
    }) async {
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: TextScaler.linear(escala)),
            child: child!,
          ),
          home: BlocProvider.value(
            value: cubit,
            child: RespostaPage(corpo: _corpo, aoAbrirCitacao: aoAbrir),
          ),
        ),
      );
      await tester.pump();
    }

    testWidgets('dose em parágrafo sem chunkIds não é renderizada', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(
          const Right(
            EventoParagrafo(
              indice: 1,
              texto: 'Dar 0,3 mg/kg por via oral.',
              chunkIds: [],
            ),
          ),
        )
        ..add(
          const Right(
            EventoParagrafo(
              indice: 2,
              texto: 'A conduta depende do estágio IRIS.',
              chunkIds: [],
            ),
          ),
        );
      await tester.pump();
      expect(find.textContaining('0,3 mg/kg'), findsNothing);
      expect(find.textContaining('Parágrafo omitido'), findsOneWidget);
      // Sem dose, o parágrafo sem lastro aparece, com o rótulo e o trilho.
      expect(find.text('A conduta depende do estágio IRIS.'), findsOneWidget);
      expect(find.text('sem lastro documental'), findsNWidgets(2));
    });

    testWidgets('dose com chunkIds é exibida', (tester) async {
      await abrir(tester);
      ctl.add(
        const Right(
          EventoParagrafo(
            indice: 1,
            texto: 'Dar 0,1 mg/kg uma vez ao dia.',
            chunkIds: ['c1'],
          ),
        ),
      );
      await tester.pump();
      expect(find.textContaining('0,1 mg/kg'), findsOneWidget);
      expect(find.text('sem lastro documental'), findsNothing);
    });

    testWidgets('âncoras só aparecem com as citações e abrem o trecho', (
      tester,
    ) async {
      Citacao? aberta;
      await abrir(tester, aoAbrir: (c) => aberta = c);
      ctl.add(const Right(_p0));
      await tester.pump();
      expect(find.byType(AncoraCitacao), findsNothing);
      ctl
        ..add(const Right(EventoCitacoes([_c1, _c2])))
        ..add(const Right(_fim));
      await tester.pump();
      // 2 no parágrafo + 2 na lista de evidência.
      expect(find.byType(AncoraCitacao), findsNWidgets(4));
      expect(
        find.textContaining('O uso repetido de meloxicam'),
        findsOneWidget,
      );
      await tester.tap(find.byType(AncoraCitacao).first);
      expect(aberta, _c1);
    });

    testWidgets('rodapé traz modelo, data e tempos; ações no fim', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(const Right(_fim));
      await tester.pump();
      expect(find.textContaining('Confiança alta · m-1 · '), findsOneWidget);
      expect(find.textContaining('5,2 s total'), findsOneWidget);
      expect(find.text('Nova consulta'), findsOneWidget);
      expect(find.text('Copiar com citações'), findsOneWidget);
    });

    testWidgets('título resume a consulta', (tester) async {
      await abrir(tester);
      expect(find.text('Meloxicam · felino · 4,2 kg'), findsOneWidget);
    });

    testWidgets('estados clínicos não levam ilustração de cão ou gato', (
      tester,
    ) async {
      await abrir(tester);
      expect(find.byType(IlustracaoVetFarmaco), findsNothing); // esperando
      ctl
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(
          const Right(
            EventoFim(
              nivelConfianca: NivelConfianca.semEvidencia,
              modelo: 'm-1',
              tempos: TemposServidor(),
            ),
          ),
        );
      await tester.pump();
      expect(find.text('Sem evidência suficiente no acervo.'), findsOneWidget);
      expect(find.byType(IlustracaoVetFarmaco), findsNothing);
    });

    testWidgets('falha e tempo esgotado também ficam sem ilustração', (
      tester,
    ) async {
      await abrir(tester);
      ctl.add(const Left(FalhaTempo('O servidor demorou demais.')));
      await tester.pump();
      expect(find.text('Tentar de novo'), findsOneWidget);
      expect(find.byType(IlustracaoVetFarmaco), findsNothing);
    });

    testWidgets('tempo esgotado mantém o parcial e oferece nova tentativa', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Left(FalhaTempo('O servidor demorou demais.')));
      await tester.pump();
      expect(find.text('Meloxicam é um AINE.'), findsOneWidget);
      expect(find.text('resposta incompleta'), findsOneWidget);
      expect(find.text('Tentar de novo'), findsOneWidget);
    });

    testWidgets('citação fantasma descarta tudo, sem texto clínico', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Left(FalhaCitacao('Resposta descartada.')));
      await tester.pump();
      expect(find.text('Meloxicam é um AINE.'), findsNothing);
      expect(find.text('Resposta descartada.'), findsOneWidget);
    });

    testWidgets('layout aguenta textScaleFactor 2.0', (tester) async {
      await abrir(tester, escala: 2);
      ctl
        ..add(const Right(_p0))
        ..add(
          const Right(
            EventoAlerta(
              severidade: SeveridadeAlerta.contraindicacao,
              texto: 'Uso repetido associado a falência renal em gatos.',
              chunkIds: ['c1'],
            ),
          ),
        )
        ..add(const Right(EventoCitacoes([_c1, _c2])))
        ..add(const Right(_fim));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });

    testWidgets('pergunta em balão à direita, com chips e avatar do app', (
      tester,
    ) async {
      await abrir(tester);
      final balao = find.text('Pode?');
      expect(balao, findsOneWidget);
      expect(find.byType(AvatarVetFarmaco), findsOneWidget);
      // Chips de espécie, peso e fármaco (o título usa o texto composto).
      expect(find.text('felino'), findsOneWidget);
      expect(find.text('4,2 kg'), findsOneWidget);
      expect(find.text('meloxicam'), findsOneWidget);
      // Balão à direita; avatar à esquerda.
      final largura =
          tester.view.physicalSize.width / tester.view.devicePixelRatio;
      expect(
        tester.getTopRight(find.byType(BalaoPergunta)).dx,
        greaterThan(largura / 2),
      );
      expect(
        tester.getTopLeft(find.byType(AvatarVetFarmaco)).dx,
        lessThan(largura / 4),
      );
      // Sem campo de resposta em continuação.
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('etapas seguem os eventos; esqueleto some no 1º parágrafo', (
      tester,
    ) async {
      await abrir(tester);
      expect(find.text('Buscando na literatura…'), findsOneWidget);
      expect(find.byType(Brilho), findsOneWidget);

      ctl.add(const Right(EventoRecuperacao(chunks: 7, ms: 120)));
      await tester.pump();
      expect(find.text('7 trechos recuperados. Redigindo…'), findsOneWidget);
      expect(find.byType(Brilho), findsOneWidget);

      ctl.add(const Right(_p0));
      await tester.pump();
      expect(find.byType(EsperaResposta), findsNothing);
      expect(find.byType(Brilho), findsNothing);
      expect(find.text('Meloxicam é um AINE.'), findsOneWidget);
    });

    testWidgets(
      'o parágrafo está na árvore no mesmo quadro, animação à parte',
      (tester) async {
        // A entrada é só visual: o texto não espera a animação terminar.
        await abrir(tester);
        ctl.add(const Right(_p0));
        await tester.pump();
        expect(find.text('Meloxicam é um AINE.'), findsOneWidget);
        final opacidade = tester.widget<Opacity>(
          find
              .ancestor(
                of: find.text('Meloxicam é um AINE.'),
                matching: find.byType(Opacity),
              )
              .first,
        );
        expect(opacidade.opacity, lessThan(1));
        await tester.pump(const Duration(milliseconds: 200));
        final fim = tester.widget<Opacity>(
          find
              .ancestor(
                of: find.text('Meloxicam é um AINE.'),
                matching: find.byType(Opacity),
              )
              .first,
        );
        expect(fim.opacity, 1);
      },
    );

    testWidgets('com animações desligadas não há brilho nem entrada', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: child!,
          ),
          home: BlocProvider.value(
            value: cubit,
            child: const RespostaPage(corpo: _corpo),
          ),
        ),
      );
      await tester.pump();
      expect(find.byType(ShaderMask), findsNothing);
      ctl.add(const Right(_p0));
      await tester.pump();
      expect(find.byType(Opacity), findsNothing);
      // Nada anima: o quadro assenta sem relógio.
      await tester.pumpAndSettle();
    });

    testWidgets('cartão de alerta abre a resposta, acima da pergunta', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(
          const Right(
            EventoAlerta(
              severidade: SeveridadeAlerta.contraindicacao,
              texto: 'Uso repetido associado a falência renal em gatos.',
              chunkIds: ['c1'],
            ),
          ),
        )
        ..add(const Right(EventoCitacoes([_c1])));
      await tester.pump();
      expect(find.byType(CartaoAlerta), findsOneWidget);
      expect(
        find.text('Uso repetido associado a falência renal em gatos.'),
        findsOneWidget,
      );
      // Chip da fonte, a partir das citações do próprio alerta.
      expect(
        find.descendant(
          of: find.byType(CartaoAlerta),
          matching: find.byType(AncoraCitacao),
        ),
        findsOneWidget,
      );
      // No topo da lista, acima do balão da pergunta; barra compacta oculta.
      expect(
        tester.getTopLeft(find.byType(CartaoAlerta)).dy,
        lessThan(tester.getTopLeft(find.byType(BalaoPergunta)).dy),
      );
      expect(find.byType(BarraAlertaCompacta), findsNothing);
    });

    testWidgets('o cartão entra com o mesmo fade dos parágrafos', (
      tester,
    ) async {
      await abrir(tester);
      ctl.add(
        const Right(
          EventoAlerta(
            severidade: SeveridadeAlerta.cautela,
            texto: 'Texto do alerta.',
            chunkIds: [],
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Texto do alerta.'), findsOneWidget);
      final opacidade = tester.widget<Opacity>(
        find
            .ancestor(
              of: find.byType(CartaoAlerta),
              matching: find.byType(Opacity),
            )
            .first,
      );
      expect(opacidade.opacity, lessThan(1));
      await tester.pump(const Duration(milliseconds: 200));
      final fim = tester.widget<Opacity>(
        find
            .ancestor(
              of: find.byType(CartaoAlerta),
              matching: find.byType(Opacity),
            )
            .first,
      );
      expect(fim.opacity, 1);
    });

    testWidgets('ao rolar além do cartão aparece a barra; um toque volta', (
      tester,
    ) async {
      await abrir(tester);
      for (var i = 1; i <= 14; i++) {
        ctl.add(
          Right(
            EventoParagrafo(
              indice: i,
              texto:
                  'Parágrafo $i. ${List.filled(12, 'texto longo').join(' ')}',
              chunkIds: const ['c1'],
            ),
          ),
        );
      }
      ctl.add(
        const Right(
          EventoAlerta(
            severidade: SeveridadeAlerta.contraindicacao,
            texto: 'Uso repetido associado a falência renal em gatos.',
            chunkIds: ['c1'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(BarraAlertaCompacta), findsNothing);

      await tester.drag(find.byType(ListView), const Offset(0, -2500));
      await tester.pumpAndSettle();
      expect(find.byType(BarraAlertaCompacta), findsOneWidget);
      expect(find.text('1 alerta de segurança · ver'), findsOneWidget);

      await tester.tap(find.byType(BarraAlertaCompacta));
      await tester.pumpAndSettle();
      expect(find.byType(BarraAlertaCompacta), findsNothing);
      expect(
        find.text('Uso repetido associado a falência renal em gatos.'),
        findsOneWidget,
      );
      final topo = tester.getTopLeft(find.byType(CartaoAlerta)).dy;
      expect(topo, greaterThanOrEqualTo(0));
    });

    testWidgets('alerta que chega com a lista rolada já mostra a barra', (
      tester,
    ) async {
      await abrir(tester);
      for (var i = 1; i <= 14; i++) {
        ctl.add(
          Right(
            EventoParagrafo(
              indice: i,
              texto:
                  'Parágrafo $i. ${List.filled(12, 'texto longo').join(' ')}',
              chunkIds: const ['c1'],
            ),
          ),
        );
      }
      await tester.pumpAndSettle();
      await tester.drag(find.byType(ListView), const Offset(0, -1500));
      await tester.pumpAndSettle();
      expect(find.byType(BarraAlertaCompacta), findsNothing);

      ctl.add(
        const Right(
          EventoAlerta(
            severidade: SeveridadeAlerta.cautela,
            texto: 'Alerta tardio.',
            chunkIds: [],
          ),
        ),
      );
      await tester.pumpAndSettle();
      // O conteúdo nunca fica escondido sem um caminho de um toque.
      expect(find.byType(BarraAlertaCompacta), findsOneWidget);
    });

    testWidgets('fim da consulta: sem continuação, com Nova consulta', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(const Right(_fim));
      await tester.pump();
      expect(
        find.text(
          'Cada consulta é independente: o sistema não guarda a conversa.',
        ),
        findsOneWidget,
      );
      expect(find.text('Nova consulta'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('rodapé abre detalhes extras sem esconder a linha do roteiro', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(
          const Right(
            EventoFim(
              nivelConfianca: NivelConfianca.alta,
              modelo: 'm-1',
              tempos: TemposServidor(
                primeiroParagrafoValidado: 1400,
                total: 5200,
              ),
              thinkingLevel: 'high',
              inputTokens: 4886,
              outputTokens: 534,
              thoughtTokens: 1914,
              custoUsd: 0.0123,
            ),
          ),
        );
      await tester.pump();
      expect(find.textContaining('Confiança alta · m-1 · '), findsOneWidget);
      expect(find.text('Raciocínio: high'), findsNothing);

      await tester.tap(find.byIcon(Icons.expand_more));
      await tester.pumpAndSettle();
      expect(find.text('Raciocínio: high'), findsOneWidget);
      expect(
        find.text('Tokens: 4886 entrada · 534 saída · 1914 raciocínio'),
        findsOneWidget,
      );
      expect(find.text(r'Custo estimado: US$ 0,0123'), findsOneWidget);
      expect(find.textContaining('Confiança alta · m-1 · '), findsOneWidget);
    });

    testWidgets('rodapé sem detalhes extras não tem recolhimento', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(const Right(_fim));
      await tester.pump();
      expect(find.byIcon(Icons.expand_more), findsNothing);
    });
  });
}
