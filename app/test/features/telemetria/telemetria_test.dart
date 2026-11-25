import 'dart:async';
import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/telemetria/data/repositories/telemetria_repository_impl.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:app/features/telemetria/domain/csv_telemetria.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:app/features/telemetria/domain/ttft_stopwatch.dart';
import 'package:app/features/telemetria/domain/usecases/exportar_telemetria.dart';
import 'package:app/features/telemetria/domain/usecases/listar_telemetria.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_cubit.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_state.dart';
import 'package:app/features/telemetria/presentation/pages/telemetria_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:mocktail/mocktail.dart';

import '../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

class _Compartilhador implements CompartilhadorCsv {
  String? nome;
  String? conteudo;
  Either<Failure, Unit> resultado = const Right(unit);

  @override
  Future<Either<Failure, Unit>> compartilhar(
    String nome,
    String conteudo,
  ) async {
    this.nome = nome;
    this.conteudo = conteudo;
    return resultado;
  }
}

const _corpo = CorpoConsulta(pergunta: 'Pode?', complexidadeDica: 'baixa');

final _registro = RegistroTelemetria(
  consultaId: '1',
  data: DateTime.utc(2026, 3, 12, 9, 5),
  modelo: 'm-1',
  thinkingLevel: 'high',
  rede: 'wifi',
  condicaoCampanha: CondicaoCampanha.g4,
  desfecho: DesfechoConsulta.concluida,
  nivelConfianca: 'alta',
  primeiroEventoMs: 300,
  ttftMs: 1800,
  totalClienteMs: 5400,
  primeiroTokenServidorMs: 900,
  primeiroParagrafoValidadoServidorMs: 1400.5,
  totalServidorMs: 5200,
  inputTokens: 100,
  outputTokens: 50,
  thoughtTokens: 20,
  custoUsd: 0.0012,
  chunks: 12,
  paragrafos: 3,
);

void main() {
  group('TtftStopwatch', () {
    test('separa primeiro evento e primeiro parágrafo com texto', () {
      var agora = 1000;
      final c = TtftStopwatch(agoraMs: () => agora)..iniciar();
      agora = 1300;
      c.registrar(const EventoRecuperacao(chunks: 5, ms: 1));
      agora = 1500;
      c.registrar(
        const EventoParagrafo(indice: 1, texto: '   ', chunkIds: ['a']),
      );
      expect(c.ttftMs, isNull, reason: 'parágrafo em branco não conta');
      agora = 2900;
      c.registrar(
        const EventoParagrafo(indice: 2, texto: 'Texto.', chunkIds: ['a']),
      );
      agora = 3100;
      c.registrar(
        const EventoParagrafo(indice: 3, texto: 'Outro.', chunkIds: ['a']),
      );
      expect(c.primeiroEventoMs, 300);
      expect(c.ttftMs, 1900);
      expect(c.totalMs, 2100);
    });

    test('iniciar zera as medições', () {
      var agora = 0;
      final c = TtftStopwatch(agoraMs: () => agora)..iniciar();
      agora = 10;
      c
        ..registrar(
          const EventoParagrafo(indice: 1, texto: 'x', chunkIds: ['a']),
        )
        ..iniciar();
      expect(c.ttftMs, isNull);
      expect(c.primeiroEventoMs, isNull);
    });
  });

  group('gerarCsv', () {
    test('cabeçalho, ordem das colunas e campos separados', () {
      final linhas = gerarCsv([_registro]).trimRight().split('\n');
      expect(linhas, hasLength(2));
      final cab = linhas[0].split(',');
      final dados = linhas[1].split(',');
      expect(cab, colunasCsv);
      expect(dados, hasLength(cab.length));
      Map<String, String> m() => {
        for (var i = 0; i < cab.length; i++) cab[i]: dados[i],
      };
      expect(m()['modelo_versao'], 'm-1');
      expect(m()['thinking_level'], 'high');
      expect(m()['rede'], 'wifi');
      expect(m()['condicao_campanha'], '4g');
      expect(m()['data'], '2026-03-12T09:05:00.000Z');
      expect(m()['ttft_ms'], '1800');
      expect(m()['primeiro_evento_ms'], '300');
      expect(m()['primeiro_paragrafo_validado_servidor_ms'], '1400.5');
      expect(m()['custo_latencia_validacao_ms'], '500.5');
      expect(m()['thought_tokens'], '20');
      expect(m()['custo_usd'], '0.0012');
      expect(m()['desfecho'], 'concluida');
    });

    test('vazios ficam em branco e texto com vírgula é escapado', () {
      final r = RegistroTelemetria(
        consultaId: 'a,"b"',
        data: DateTime.utc(2026),
        rede: 'wifi',
        desfecho: DesfechoConsulta.falha,
        totalClienteMs: 10,
        falha: 'FalhaRede',
      );
      final linha = gerarCsv([r]).trimRight().split('\n')[1];
      expect(
        linha,
        startsWith(
          '"a,""b""",2026-01-01T00:00:00.000Z,,,wifi,nao_informada,falha',
        ),
      );
      expect(r.custoLatenciaValidacaoMs, isNull);
      expect(linha, endsWith(',0,FalhaRede'));
    });
  });

  group('TelemetriaRepositoryImpl', () {
    late Directory dir;
    late Box<dynamic> caixa;

    setUp(() async {
      dir = Directory.systemTemp.createTempSync('telemetria_test');
      Hive.init(dir.path);
      caixa = await Hive.openBox<dynamic>('telemetria');
    });

    tearDown(() async {
      await Hive.close();
      dir.deleteSync(recursive: true);
    });

    test('grava, lista em ordem de data e sobrevive à reabertura', () async {
      final repo = TelemetriaRepositoryImpl(caixa);
      final antigo = RegistroTelemetria(
        consultaId: '0',
        data: DateTime.utc(2026),
        rede: 'mobile',
        desfecho: DesfechoConsulta.semEvidencia,
        totalClienteMs: 9,
      );
      await repo.gravar(_registro);
      await repo.gravar(antigo);
      var lista = (await repo.listar()).getOrElse((_) => []);
      expect(lista, [antigo, _registro]);

      await Hive.close();
      final reaberta = await Hive.openBox<dynamic>('telemetria');
      lista = (await TelemetriaRepositoryImpl(
        reaberta,
      ).listar()).getOrElse((_) => []);
      expect(lista, [antigo, _registro]);
    });

    test('dado corrompido vira FalhaCache', () async {
      await caixa.put('x', 'não é json');
      final r = await TelemetriaRepositoryImpl(caixa).listar();
      expect(r.getLeft().toNullable(), isA<FalhaCache>());
    });
  });

  group('ExportarTelemetria', () {
    test('sem registros não compartilha', () async {
      final c = _Compartilhador();
      final r = await ExportarTelemetria(TelemetriaEmMemoria(), c)();
      expect(r.getLeft().toNullable(), isA<FalhaValidacao>());
      expect(c.nome, isNull);
    });

    test('compartilha o CSV de todos os registros', () async {
      final repo = TelemetriaEmMemoria();
      await repo.gravar(_registro);
      final c = _Compartilhador();
      final r = await ExportarTelemetria(repo, c)();
      expect(r.getOrElse((_) => 0), 1);
      expect(c.nome, 'telemetria_vetfarmaco.csv');
      expect(c.conteudo, gerarCsv([_registro]));
    });

    test('propaga a falha do compartilhamento', () async {
      final repo = TelemetriaEmMemoria();
      await repo.gravar(_registro);
      final c = _Compartilhador()
        ..resultado = const Left(FalhaCache('sem share'));
      final r = await ExportarTelemetria(repo, c)();
      expect(r.getLeft().toNullable(), isA<FalhaCache>());
    });
  });

  group('RespostaCubit grava telemetria', () {
    late _MockRealizar realizar;
    late StreamController<Either<Failure, EventoResposta>> ctl;
    late TelemetriaEmMemoria memoria;
    late RespostaCubit cubit;
    late int relogio;

    setUp(() {
      realizar = _MockRealizar();
      ctl = StreamController.broadcast();
      when(() => realizar(_corpo)).thenAnswer((_) => ctl.stream);
      memoria = TelemetriaEmMemoria();
      relogio = 0;
      cubit = novoRespostaCubit(realizar, telemetria: memoria, rede: 'mobile')
        ..criarRelogio = (() => TtftStopwatch(agoraMs: () => relogio))
        ..agora = (() => DateTime.utc(2026, 3, 12));
    });

    tearDown(() async {
      await cubit.close();
      await ctl.close();
    });

    Future<void> enviar(Either<Failure, EventoResposta> e, int em) async {
      relogio = em;
      ctl.add(e);
      await Future<void>.delayed(Duration.zero);
    }

    test(
      'consulta concluída: tempos separados, modelo, data e custo',
      () async {
        await cubit.iniciar(_corpo);
        await enviar(const Right(EventoRecuperacao(chunks: 12, ms: 1)), 300);
        await enviar(
          const Right(
            EventoParagrafo(indice: 1, texto: 'Texto.', chunkIds: ['c']),
          ),
          1800,
        );
        await enviar(
          const Right(
            EventoFim(
              nivelConfianca: NivelConfianca.alta,
              modelo: 'm-1',
              tempos: TemposServidor(
                primeiroToken: 900,
                primeiroParagrafoValidado: 1400,
                total: 5200,
              ),
              inputTokens: 100,
              outputTokens: 50,
              thoughtTokens: 20,
              custoUsd: 0.002,
            ),
          ),
          5400,
        );
        await Future<void>.delayed(Duration.zero);
        final r = memoria.registros.single;
        expect(r.desfecho, DesfechoConsulta.concluida);
        expect(r.modelo, 'm-1');
        expect(r.data, DateTime.utc(2026, 3, 12));
        expect(r.rede, 'mobile');
        expect(r.primeiroEventoMs, 300);
        expect(r.ttftMs, 1800);
        expect(r.totalClienteMs, 5400);
        expect(r.custoLatenciaValidacaoMs, 500);
        expect(r.thoughtTokens, 20);
        expect(r.chunks, 12);
        expect(r.paragrafos, 1);
      },
    );

    test('sem evidência: registrada, sem TTFT', () async {
      await cubit.iniciar(_corpo);
      await enviar(const Right(EventoRecuperacao(chunks: 4, ms: 1)), 200);
      await enviar(
        const Right(
          EventoFim(
            nivelConfianca: NivelConfianca.semEvidencia,
            modelo: 'm-1',
            tempos: TemposServidor(),
          ),
        ),
        900,
      );
      await Future<void>.delayed(Duration.zero);
      final r = memoria.registros.single;
      expect(r.desfecho, DesfechoConsulta.semEvidencia);
      expect(r.ttftMs, isNull);
      expect(r.chunks, 4);
    });

    test('citação fantasma é falha; queda com parcial é incompleta', () async {
      await cubit.iniciar(_corpo);
      await enviar(const Left(FalhaCitacao('x')), 700);
      await Future<void>.delayed(Duration.zero);
      expect(memoria.registros.single.desfecho, DesfechoConsulta.falha);
      expect(memoria.registros.single.falha, 'FalhaCitacao');
      expect(memoria.registros.single.modelo, isNull);

      memoria.registros.clear();
      relogio = 0;
      await cubit.iniciar(_corpo);
      await enviar(
        const Right(
          EventoParagrafo(indice: 1, texto: 'Texto.', chunkIds: ['c']),
        ),
        1500,
      );
      await enviar(const Left(FalhaTempo('t')), 31000);
      await Future<void>.delayed(Duration.zero);
      final r = memoria.registros.single;
      expect(r.desfecho, DesfechoConsulta.incompleta);
      expect(r.ttftMs, 1500);
      expect(r.paragrafos, 1);
    });
  });

  group('TelemetriaPage', () {
    testWidgets('mostra a contagem e exporta', (tester) async {
      final repo = TelemetriaEmMemoria();
      await repo.gravar(_registro);
      final comp = _Compartilhador();
      final cubit = TelemetriaCubit(
        ListarTelemetria(repo),
        ExportarTelemetria(repo, comp),
      );
      addTearDown(cubit.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(value: cubit, child: const TelemetriaPage()),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('1'), findsOneWidget);
      await tester.tap(find.text('Exportar CSV'));
      await tester.pumpAndSettle();
      expect(comp.conteudo, isNotNull);
      expect(cubit.state.status, StatusTelemetria.pronta);
    });

    testWidgets('sem registros o botão fica desabilitado', (tester) async {
      final repo = TelemetriaEmMemoria();
      final cubit = TelemetriaCubit(
        ListarTelemetria(repo),
        ExportarTelemetria(repo, _Compartilhador()),
      );
      addTearDown(cubit.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(value: cubit, child: const TelemetriaPage()),
        ),
      );
      await tester.pumpAndSettle();
      final botao = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(botao.onPressed, isNull);
    });
  });
}
