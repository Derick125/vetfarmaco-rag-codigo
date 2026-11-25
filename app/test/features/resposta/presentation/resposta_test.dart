import 'dart:async';

import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/resposta/presentation/pages/resposta_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';

import 'package:mocktail/mocktail.dart';

import '../../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

const _corpo = CorpoConsulta(pergunta: 'Pode?', complexidadeDica: 'baixa');

const _p0 = EventoParagrafo(indice: 0, texto: 'Primeiro.', chunkIds: ['c1']);
const _p1 = EventoParagrafo(indice: 1, texto: 'Segundo.', chunkIds: []);
const _fim = EventoFim(
  nivelConfianca: NivelConfianca.alta,
  modelo: 'm-1',
  tempos: TemposServidor(),
);

void main() {
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

  Future<void> emitir(EventoResposta e) async {
    ctl.add(Right(e));
    await Future<void>.delayed(Duration.zero);
  }

  Future<void> falhar(Failure f) async {
    ctl.add(Left(f));
    await Future<void>.delayed(Duration.zero);
  }

  group('RespostaCubit', () {
    test('acumula parágrafos, citações e alerta até o fim', () async {
      await cubit.iniciar(_corpo);
      expect(cubit.state.fase, FaseResposta.recuperando);
      await emitir(const EventoRecuperacao(chunks: 12, ms: 1));
      expect(cubit.state.chunks, 12);
      expect(cubit.state.fase, FaseResposta.recuperando);
      await emitir(_p0);
      await emitir(_p1);
      expect(cubit.state.fase, FaseResposta.transmitindo);
      expect(cubit.state.paragrafos, [_p0, _p1]);
      await emitir(
        const EventoAlerta(
          severidade: SeveridadeAlerta.cautela,
          texto: 'a',
          chunkIds: ['c1'],
        ),
      );
      await emitir(_fim);
      expect(cubit.state.fase, FaseResposta.concluida);
      expect(cubit.state.alerta, isNotNull);
      expect(cubit.state.fim, _fim);
    });

    test('fim sem evidência descarta os parágrafos e não é falha', () async {
      await cubit.iniciar(_corpo);
      await emitir(const EventoRecuperacao(chunks: 4, ms: 1));
      await emitir(_p0);
      await emitir(
        const EventoFim(
          nivelConfianca: NivelConfianca.semEvidencia,
          modelo: 'm-1',
          tempos: TemposServidor(),
        ),
      );
      expect(cubit.state.fase, FaseResposta.semEvidencia);
      expect(cubit.state.paragrafos, isEmpty);
      expect(cubit.state.mensagem, isNull);
    });

    test('citação fantasma descarta tudo o que já chegou', () async {
      await cubit.iniciar(_corpo);
      await emitir(_p0);
      await falhar(const FalhaCitacao('descartada'));
      expect(cubit.state.fase, FaseResposta.falha);
      expect(cubit.state.paragrafos, isEmpty);
      expect(cubit.state.mensagem, 'descartada');
    });

    test('queda de rede mantém o parcial marcado como incompleto', () async {
      await cubit.iniciar(_corpo);
      await emitir(_p0);
      await falhar(const FalhaTempo('demorou'));
      expect(cubit.state.fase, FaseResposta.falha);
      expect(cubit.state.paragrafos, [_p0]);
      expect(cubit.state.incompleta, isTrue);
    });
  });

  group('RespostaPage', () {
    Future<void> abrir(WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(
            value: cubit,
            child: const RespostaPage(corpo: _corpo),
          ),
        ),
      );
      await tester.pump();
    }

    testWidgets('mostra a etapa, os parágrafos conforme chegam e o rodapé', (
      tester,
    ) async {
      await abrir(tester);
      expect(find.text('Buscando na literatura…'), findsOneWidget);
      ctl.add(const Right(EventoRecuperacao(chunks: 12, ms: 1)));
      await tester.pump();
      expect(find.text('12 trechos recuperados. Redigindo…'), findsOneWidget);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(_p1));
      await tester.pump();
      expect(find.text('Primeiro.'), findsOneWidget);
      expect(find.text('Segundo.'), findsOneWidget);
      expect(find.text('sem lastro documental'), findsOneWidget);
      expect(find.textContaining('ao final da resposta'), findsOneWidget);
      ctl.add(const Right(_fim));
      await tester.pump();
      expect(find.textContaining('Confiança alta · m-1'), findsOneWidget);
    });

    testWidgets('alerta aparece antes do primeiro parágrafo', (tester) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
        ..add(
          const Right(
            EventoAlerta(
              severidade: SeveridadeAlerta.contraindicacao,
              texto: 'Evitar.',
              chunkIds: ['c1'],
            ),
          ),
        );
      await tester.pump();
      final alerta = tester.getTopLeft(find.text('Contraindicação'));
      final paragrafo = tester.getTopLeft(find.text('Primeiro.'));
      expect(alerta.dy, lessThan(paragrafo.dy));
    });

    testWidgets('sem evidência mostra o estado legítimo, sem parágrafos', (
      tester,
    ) async {
      await abrir(tester);
      ctl
        ..add(const Right(_p0))
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
      expect(find.textContaining('Sem evidência suficiente'), findsOneWidget);
      expect(find.text('Primeiro.'), findsNothing);
    });

    testWidgets('falha mostra a mensagem', (tester) async {
      await abrir(tester);
      ctl.add(const Left(FalhaCota('Cota atingida.')));
      await tester.pump();
      expect(find.text('Cota atingida.'), findsOneWidget);
    });
  });
}
