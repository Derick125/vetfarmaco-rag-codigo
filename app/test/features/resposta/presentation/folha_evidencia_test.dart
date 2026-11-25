import 'dart:async';

import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/pages/resposta_page.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:app/features/resposta/presentation/widgets/folha_evidencia.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';

import 'package:mocktail/mocktail.dart';

import '../../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

const _corpo = CorpoConsulta(pergunta: 'Pode?', complexidadeDica: 'baixa');

const _completa = Citacao(
  chunkId: 'spinosa-22-0007',
  indice: 1,
  trecho:
      'O uso repetido de meloxicam em gatos foi associado a falência renal.',
  fonte: 'Spinosa et al. (2017)',
  capitulo: '22',
  pagina: 311,
);
const _minima = Citacao(
  chunkId: 'bula-0001',
  indice: 2,
  trecho: 'Bula.',
  fonte: 'Bula — meloxicam',
);

void main() {
  testWidgets('folha mostra trecho, fonte, capítulo, página e chunk_id', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () =>
                  unawaited(abrirFolhaEvidencia(context, _completa)),
              child: const Text('abrir'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('abrir'));
    await tester.pumpAndSettle();

    expect(find.text('Trecho recuperado 1'), findsOneWidget);
    expect(find.textContaining('falência renal'), findsOneWidget);
    expect(find.text('Spinosa et al. (2017)'), findsOneWidget);
    expect(find.text('22'), findsOneWidget);
    expect(find.text('311'), findsOneWidget);
    expect(find.text('spinosa-22-0007'), findsOneWidget);

    await tester.tap(find.byTooltip('Fechar'));
    await tester.pumpAndSettle();
    expect(find.text('Trecho recuperado 1'), findsNothing);
  });

  testWidgets('capítulo e página ausentes não geram linhas', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: FolhaEvidencia(citacao: _minima)),
      ),
    );
    expect(find.text('Capítulo'), findsNothing);
    expect(find.text('Página'), findsNothing);
    expect(find.text('bula-0001'), findsOneWidget);
  });

  testWidgets('tocar a âncora na resposta abre a folha do trecho', (
    tester,
  ) async {
    final realizar = _MockRealizar();
    final ctl = StreamController<Either<Failure, EventoResposta>>();
    when(() => realizar(_corpo)).thenAnswer((_) => ctl.stream);
    final cubit = novoRespostaCubit(realizar);
    addTearDown(() async {
      await cubit.close();
      await ctl.close();
    });
    await tester.pumpWidget(
      MaterialApp(
        home: BlocProvider.value(
          value: cubit,
          child: const RespostaPage(corpo: _corpo),
        ),
      ),
    );
    ctl
      ..add(
        const Right(
          EventoParagrafo(
            indice: 1,
            texto: 'Texto.',
            chunkIds: ['spinosa-22-0007'],
          ),
        ),
      )
      ..add(const Right(EventoCitacoes([_completa])))
      ..add(
        const Right(
          EventoFim(
            nivelConfianca: NivelConfianca.alta,
            modelo: 'm',
            tempos: TemposServidor(),
          ),
        ),
      );
    await tester.pump();

    await tester.tap(find.byType(AncoraCitacao).first);
    await tester.pumpAndSettle();
    expect(find.byType(FolhaEvidencia), findsOneWidget);
    expect(find.text('spinosa-22-0007'), findsOneWidget);
  });
}
