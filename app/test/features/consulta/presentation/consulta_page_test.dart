import 'package:app/core/error/failures.dart';
import 'package:app/core/privacy/sanitizador_regex.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/usecases/obter_vocabulario.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_cubit.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_state.dart';
import 'package:app/features/consulta/presentation/pages/consulta_page.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

class _MockObter extends Mock implements ObterVocabulario;

const _vocab = Vocabulario(
  versao: 'v1',
  especies: ['canino', 'felino'],
  farmacos: [
    FarmacoVocabulario(nome: 'meloxicam', sinonimos: ['Metacam']),
    FarmacoVocabulario(nome: 'furosemida'),
  ],
  comorbidades: [
    ComorbidadeVocabulario(chave: 'epilepsia', rotulo: 'epilepsia'),
    ComorbidadeVocabulario(chave: 'gestacao', rotulo: 'gestação'),
  ],
);

void main() {
  late _MockObter obter;

  setUp(() {
    obter = _MockObter();
    when(obter.call).thenAnswer((_) async => const Right(_vocab));
  });

  group('ConsultaCubit', () {
    blocTest<ConsultaCubit, ConsultaState>(
      'carregar publica o vocabulário',
      build: () =>
          ConsultaCubit(obter, const MontarCorpoConsulta(SanitizadorRegex())),
      act: (c) => c.carregar(),
      expect: () => [
        const ConsultaState(),
        const ConsultaState(
          status: StatusVocabulario.pronto,
          vocabulario: _vocab,
        ),
      ],
    );

    blocTest<ConsultaCubit, ConsultaState>(
      'carregar com falha publica a mensagem',
      setUp: () =>
          when(obter.call)
              .thenAnswer((_) async => const Left(FalhaRede('sem rede'))),
      build: () =>
          ConsultaCubit(obter, const MontarCorpoConsulta(SanitizadorRegex())),
      act: (c) => c.carregar(),
      verify: (c) {
        expect(c.state.status, StatusVocabulario.falha);
        expect(c.state.mensagem, 'sem rede');
      },
    );

    test('espécie alterna, fármacos não repetem, comorbidade alterna', () {
      final c =
          ConsultaCubit(obter, const MontarCorpoConsulta(SanitizadorRegex()))
            ..alterarEspecie('felino')
            ..adicionarFarmaco('meloxicam')
            ..adicionarFarmaco('meloxicam')
            ..adicionarFarmaco('furosemida')
            ..alternarComorbidade('epilepsia')
            ..alterarPeso('4,2');
      expect(c.state.formulario.especie, 'felino');
      expect(c.state.formulario.farmacos, ['meloxicam', 'furosemida']);
      expect(c.state.formulario.comorbidades, {'epilepsia'});
      expect(c.state.formulario.peso, 4.2);
      c
        ..alterarEspecie('felino')
        ..removerFarmaco('meloxicam')
        ..alternarComorbidade('epilepsia');
      expect(c.state.formulario.especie, isNull);
      expect(c.state.formulario.farmacos, ['furosemida']);
      expect(c.state.formulario.comorbidades, isEmpty);
    });
  });

  group('ConsultaPage', () {
    Future<ConsultaCubit> abrir(WidgetTester tester) async {
      final cubit = ConsultaCubit(
        obter,
        const MontarCorpoConsulta(SanitizadorRegex()),
      );
      addTearDown(cubit.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(value: cubit, child: const ConsultaPage()),
        ),
      );
      await tester.pumpAndSettle();
      return cubit;
    }

    testWidgets('a nova consulta não tem ilustração nem imagem', (
      tester,
    ) async {
      // Início do caminho medido: nenhuma imagem entra aqui (SPEC §26).
      await abrir(tester);
      expect(find.byType(IlustracaoVetFarmaco), findsNothing);
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('mostra os campos do vocabulário', (tester) async {
      await abrir(tester);
      expect(find.text('Canino'), findsOneWidget);
      expect(find.text('Felino'), findsOneWidget);
      expect(find.text('gestação'), findsOneWidget);
      expect(find.textContaining('ao menos um fármaco'), findsOneWidget);
    });

    testWidgets('aviso de PII fica acima do campo da pergunta', (tester) async {
      await abrir(tester);
      final aviso = find.text(
        'Não inclua nomes de tutores, de animais ou números de prontuário.',
      );
      expect(aviso, findsOneWidget);
      expect(
        tester.getBottomLeft(aviso).dy,
        lessThan(tester.getTopLeft(find.byType(TextField).last).dy),
      );
    });

    testWidgets('espécie, comorbidade e fármaco por autocomplete', (
      tester,
    ) async {
      final cubit = await abrir(tester);
      await tester.tap(find.text('Felino'));
      await tester.tap(find.text('epilepsia'));
      await tester.enterText(find.byType(TextField).at(1), 'metac');
      await tester.pumpAndSettle();
      await tester.tap(find.text('meloxicam').last);
      await tester.pumpAndSettle();

      final f = cubit.state.formulario;
      expect(f.especie, 'felino');
      expect(f.comorbidades, {'epilepsia'});
      expect(f.farmacos, ['meloxicam']);
      expect(find.byType(InputChip), findsOneWidget);
      expect(find.textContaining('ao menos um fármaco'), findsNothing);

      await tester.tap(find.byTooltip('Remover meloxicam'));
      await tester.pumpAndSettle();
      expect(cubit.state.formulario.farmacos, isEmpty);
    });

    testWidgets('pergunta com PII aparece mascarada na prévia', (tester) async {
      await abrir(tester);
      await tester.tap(find.text('Felino'));
      await tester.enterText(
        find.byType(TextField).at(2),
        'Dose de meloxicam? CPF 123.456.789-09 tel 85 98765-4321',
      );
      await tester.pump();
      await tester.drag(find.byType(ListView), const Offset(0, -600));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ver o que será enviado'));
      await tester.pumpAndSettle();
      final json = tester.widget<SelectableText>(find.byType(SelectableText));
      expect(json.data, contains('[CPF]'));
      expect(json.data, contains('[TELEFONE]'));
      expect(json.data, isNot(contains('123.456')));
      expect(json.data, contains('"especie": "felino"'));
      expect(json.data, contains('"complexidade_dica": "baixa"'));
    });

    testWidgets('botão só habilita com espécie e pergunta válidas', (
      tester,
    ) async {
      await abrir(tester);
      FilledButton botao() => tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Consultar a literatura'),
      );
      await tester.drag(find.byType(ListView), const Offset(0, -600));
      await tester.pumpAndSettle();
      expect(botao().onPressed, isNull);
      await tester.enterText(find.byType(TextField).at(2), 'É seguro?');
      await tester.pump();
      expect(botao().onPressed, isNull, reason: 'falta a espécie');
      await tester.drag(find.byType(ListView), const Offset(0, 600));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Felino'));
      await tester.drag(find.byType(ListView), const Offset(0, -600));
      await tester.pumpAndSettle();
      expect(botao().onPressed, isNotNull);
    });

    testWidgets('peso inválido mostra erro', (tester) async {
      await abrir(tester);
      await tester.enterText(find.byType(TextField).first, '250');
      await tester.pump();
      expect(find.text('Informe um peso entre 0 e 200 kg.'), findsOneWidget);
    });

    testWidgets('falha oferece nova tentativa', (tester) async {
      var chamadas = 0;
      when(obter.call).thenAnswer((_) async {
        chamadas++;
        return chamadas == 1
            ? const Left(FalhaRede('Sem conexão com o servidor.'))
            : const Right(_vocab);
      });
      await abrir(tester);
      expect(find.text('Sem conexão com o servidor.'), findsOneWidget);
      await tester.tap(find.text('Tentar de novo'));
      await tester.pumpAndSettle();
      expect(find.text('Canino'), findsOneWidget);
    });
  });
}
