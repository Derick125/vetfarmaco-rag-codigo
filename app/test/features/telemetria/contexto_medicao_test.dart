import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/data/repositories/ajustes_repository_impl.dart';
import 'package:app/features/ajustes/domain/saude_backend.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:app/features/telemetria/domain/contexto_medicao.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/usecases/capturar_contexto_medicao.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:mocktail/mocktail.dart';

import '../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

class _Adaptador implements HttpClientAdapter {
  new({this.corpo, this.status = 200, this.erro});

  final Object? corpo;
  final int status;
  final DioExceptionType? erro;
  int chamadas = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    chamadas++;
    if (erro != null) throw DioException(requestOptions: options, type: erro!);
    return ResponseBody.fromString(
      jsonEncode(corpo),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _Configuracao implements ConfiguracaoRepository {
  new(this.endereco);

  final String? endereco;

  @override
  Future<String?> enderecoBackend() async => endereco;

  @override
  Future<DateTime?> termoAceitoEm() async => null;
}

const _corpo = CorpoConsulta(pergunta: 'Pode?', complexidadeDica: 'baixa');

void main() {
  late Directory dir;
  late Box<dynamic> caixa;

  setUpAll(() => registerFallbackValue(_corpo));

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('contexto_test');
    Hive.init(dir.path);
    caixa = await Hive.openBox<dynamic>('configuracao');
  });

  tearDown(() async {
    await Hive.close();
    dir.deleteSync(recursive: true);
  });

  AjustesRepositoryImpl repo(_Adaptador a) =>
      AjustesRepositoryImpl(caixa, Dio()..httpClientAdapter = a);

  group('AjustesRepositoryImpl: /health e condição da campanha', () {
    test('consultarSaude lê o modelo_id do /health', () async {
      final r = await repo(
        _Adaptador(corpo: {'status': 'ok', 'modelo_id': 'm-9'}),
      ).consultarSaude('http://x');
      expect(r.toNullable(), const SaudeBackend(modeloId: 'm-9'));
    });

    test('modelo_id null, ausente ou de tipo errado vira null', () async {
      for (final corpo in [
        {'status': 'ok', 'modelo_id': null},
        {'status': 'ok'},
        {'status': 'ok', 'modelo_id': 7},
        <String, dynamic>{},
      ]) {
        final r = await repo(_Adaptador(corpo: corpo))
            .consultarSaude('http://x');
        expect(r.toNullable(), const SaudeBackend(), reason: '$corpo');
      }
    });

    test('corpo que não é objeto não derruba (health antigo)', () async {
      final r = await repo(_Adaptador(corpo: 'ok')).consultarSaude('http://x');
      expect(r.toNullable(), const SaudeBackend());
    });

    test('falhas do /health seguem o mapeamento de sempre', () async {
      final r = await repo(_Adaptador(status: 503)).consultarSaude('http://x');
      expect(r.getLeft().toNullable(), isA<FalhaServidor>());
    });

    test('condição: padrão não informada, grava e relê', () async {
      final a = repo(_Adaptador());
      expect(await a.condicaoCampanha(), CondicaoCampanha.naoInformada);
      await a.salvarCondicaoCampanha(CondicaoCampanha.g5);
      expect(await a.condicaoCampanha(), CondicaoCampanha.g5);
      expect(caixa.get(chaveCondicaoCampanha), 'g5');
    });

    test('valor corrompido na caixa volta a não informada', () async {
      await caixa.put(chaveCondicaoCampanha, 'banda-larga');
      expect(
        await repo(_Adaptador()).condicaoCampanha(),
        CondicaoCampanha.naoInformada,
      );
    });

    test('gravar com a caixa fechada vira FalhaCache', () async {
      final a = repo(_Adaptador());
      await caixa.close();
      final r = await a.salvarCondicaoCampanha(CondicaoCampanha.wifi);
      expect(r.getLeft().toNullable(), isA<FalhaCache>());
    });
  });

  group('CapturarContextoMedicao', () {
    CapturarContextoMedicao captura(
      _Adaptador a, {
      String? endereco = 'http://srv:8000/',
      String rede = 'mobile',
    }) => CapturarContextoMedicao(
      RedeFalsa(rede),
      repo(a),
      ObterEnderecoBackend(_Configuracao(endereco)),
    );

    test('reúne rede, condição salva e modelo do /health', () async {
      await repo(_Adaptador()).salvarCondicaoCampanha(CondicaoCampanha.g4);
      final a = _Adaptador(corpo: {'status': 'ok', 'modelo_id': 'm-1'});
      final c = await captura(a)();
      expect(
        c,
        const ContextoMedicao(
          rede: 'mobile',
          condicao: CondicaoCampanha.g4,
          modelo: 'm-1',
        ),
      );
      expect(a.chamadas, 1);
    });

    test('back-end fora do ar: segue sem modelo, nunca lança', () async {
      final c = await captura(
        _Adaptador(erro: DioExceptionType.connectionError),
      )();
      expect(c.modelo, isNull);
      expect(c.rede, 'mobile');
    });

    test('sem rede, vale o último modelo que o /health informou', () async {
      await captura(_Adaptador(corpo: {'modelo_id': 'm-antigo'}))();
      expect(caixa.get(chaveUltimoModelo), 'm-antigo');
      final c = await captura(
        _Adaptador(erro: DioExceptionType.connectionError),
      )();
      expect(c.modelo, 'm-antigo');
    });

    test('sem endereço ou endereço inválido: nem chama o /health', () async {
      final a = _Adaptador(corpo: {'modelo_id': 'm'});
      expect((await captura(a, endereco: null)()).modelo, isNull);
      expect((await captura(a, endereco: 'lixo')()).modelo, isNull);
      expect(a.chamadas, 0);
    });
  });

  group('RespostaCubit grava modelo e condição no registro', () {
    late _MockRealizar realizar;
    late StreamController<Either<Failure, EventoResposta>> ctl;
    late TelemetriaEmMemoria memoria;

    setUp(() {
      realizar = _MockRealizar();
      ctl = StreamController.broadcast();
      when(() => realizar(any())).thenAnswer((_) => ctl.stream);
      memoria = TelemetriaEmMemoria();
    });

    tearDown(() => ctl.close());

    test('falha antes do fim: modelo vem do /health do envio', () async {
      final c = novoRespostaCubit(
        realizar,
        telemetria: memoria,
        rede: 'mobile',
        condicao: CondicaoCampanha.g5,
        modelo: 'm-saude',
      );
      await c.iniciar(_corpo);
      ctl.add(const Left(FalhaServidor('500')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      final r = memoria.registros.single;
      expect(r.desfecho, DesfechoConsulta.falha);
      expect(r.modelo, 'm-saude');
      expect(r.condicaoCampanha, CondicaoCampanha.g5);
      expect(r.rede, 'mobile');
      await c.close();
    });

    test('com fim, vale o modelo do fim (quem gerou a resposta)', () async {
      final c = novoRespostaCubit(
        realizar,
        telemetria: memoria,
        condicao: CondicaoCampanha.wifi,
        modelo: 'm-saude',
      );
      await c.iniciar(_corpo);
      ctl.add(
        const Right(
          EventoFim(
            nivelConfianca: NivelConfianca.alta,
            modelo: 'm-fim',
            tempos: TemposServidor(),
          ),
        ),
      );
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(memoria.registros.single.modelo, 'm-fim');
      expect(memoria.registros.single.condicaoCampanha, CondicaoCampanha.wifi);
      await c.close();
    });

    test('falha depois da recuperação: thinking_level vem dela', () async {
      final c = novoRespostaCubit(realizar, telemetria: memoria);
      await c.iniciar(_corpo);
      ctl.add(
        const Right(EventoRecuperacao(chunks: 5, ms: 1, thinkingLevel: 'high')),
      );
      await Future<void>.delayed(Duration.zero);
      ctl.add(const Left(FalhaServidor('500')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      final r = memoria.registros.single;
      expect(r.desfecho, DesfechoConsulta.falha);
      expect(r.thinkingLevel, 'high');
      await c.close();
    });

    test(
      'com fim, o thinking_level do fim vale mais que o da recuperação',
      () async {
        final c = novoRespostaCubit(realizar, telemetria: memoria);
        await c.iniciar(_corpo);
        ctl.add(
          const Right(
            EventoRecuperacao(chunks: 5, ms: 1, thinkingLevel: 'low'),
          ),
        );
        await Future<void>.delayed(Duration.zero);
        ctl.add(
          const Right(
            EventoFim(
              nivelConfianca: NivelConfianca.alta,
              modelo: 'm',
              thinkingLevel: 'high',
              tempos: TemposServidor(),
            ),
          ),
        );
        await Future<void>.delayed(Duration.zero);
        await Future<void>.delayed(Duration.zero);
        expect(memoria.registros.single.thinkingLevel, 'high');
        await c.close();
      },
    );

    test(
      'cache: modelo e thinking_level são os da resposta guardada',
      () async {
        final cache = CacheEmMemoria();
        await cache.salvar(
          RespostaSalva(
            corpo: _corpo,
            paragrafos: const [],
            citacoes: const [],
            fim: const EventoFim(
              nivelConfianca: NivelConfianca.alta,
              modelo: 'm-guardado',
              thinkingLevel: 'low',
              tempos: TemposServidor(),
            ),
            geradaEm: DateTime.utc(2026, 10, 29),
          ),
        );
        final c = novoRespostaCubit(
          realizar,
          telemetria: memoria,
          cache: cache,
        );
        await c.iniciar(_corpo);
        ctl.add(const Left(FalhaRede('offline')));
        for (var i = 0; i < 4; i++) {
          await Future<void>.delayed(Duration.zero);
        }
        final r = memoria.registros.single;
        expect(r.desfecho, DesfechoConsulta.cache);
        expect(r.modelo, 'm-guardado');
        expect(r.thinkingLevel, 'low');
        await c.close();
      },
    );

    test('sem /health e sem fim: modelo null, condição preservada', () async {
      final c = novoRespostaCubit(
        realizar,
        telemetria: memoria,
        condicao: CondicaoCampanha.g4,
      );
      await c.iniciar(_corpo);
      ctl.add(const Left(FalhaRede('offline')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(memoria.registros.single.modelo, isNull);
      expect(memoria.registros.single.condicaoCampanha, CondicaoCampanha.g4);
      await c.close();
    });
  });
}
