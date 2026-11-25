import 'dart:convert';

import 'package:app/core/config/app_config.dart';
import 'package:app/core/error/failures.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/data/datasources/rag_remote_source.dart';
import 'package:app/features/resposta/data/repositories/rag_repository_impl.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';

String _sse(String evento, Object dados) =>
    'event: $evento\r\ndata: ${jsonEncode(dados)}\r\n\r\n';

/// Stream no formato que o back-end emite (`docs/RAG_SPEC.md` §7.1).
final List<String> _feliz = [
  _sse('recuperacao', {'chunks': 12, 'ms': 410.5, 'thinkingLevel': 'low'}),
  _sse('paragrafo', {
    'indice': 0,
    'texto': 'Meloxicam é um AINE.',
    'chunkIds': ['c1'],
  }),
  _sse('citacoes', {
    'citacoes': [
      {
        'chunkId': 'c1',
        'indice': 1,
        'trecho': 'O meloxicam...',
        'fonte': 'Spinosa et al. (2017)',
        'capitulo': '22',
        'pagina': null,
      },
    ],
  }),
  _sse('alerta', {
    'severidade': 'cautela',
    'texto': 'Atenção renal.',
    'chunkIds': ['c1'],
  }),
  _sse('fim', {
    'nivelConfianca': 'sem_evidencia',
    'modelo': 'm-1',
    'thinkingLevel': 'high',
    'usage': {'inputTokens': 10, 'outputTokens': 5, 'thoughtTokens': null},
    'custoUsd': 0.001,
    'tempos': {
      'msPrimeiroToken': 900.0,
      'msPrimeiroParagrafoValidado': 1400.0,
      'msTotal': 5200.0,
    },
  }),
];

class _Adaptador implements HttpClientAdapter {
  new({this.partes = const [], this.status = 200, this.erro});

  final List<String> partes;
  final int status;
  final DioExceptionType? erro;
  RequestOptions? ultima;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    ultima = options;
    if (erro != null) throw DioException(requestOptions: options, type: erro!);
    return ResponseBody(
      Stream.fromIterable(partes.map(utf8.encode)),
      status,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
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

const _corpo = CorpoConsulta(
  pergunta: 'Pode?',
  complexidadeDica: 'baixa',
  especie: 'felino',
);

void main() {
  RagRepositoryImpl repo(_Adaptador a, {String? endereco}) => RagRepositoryImpl(
    RagRemoteSource(
      Dio()..httpClientAdapter = a,
      const AppConfig(clientApiKey: 'chave'),
    ),
    _Configuracao(endereco ?? 'http://srv:8000/'),
  );

  Future<List<Either<Failure, EventoResposta>>> rodar(
    _Adaptador a, {
    String? endereco,
  }) => repo(a, endereco: endereco).consultar(_corpo).toList();

  test(
    'mapeia todos os eventos do contrato e envia X-API-Key e corpo',
    () async {
      final a = _Adaptador(partes: _feliz);
      final r = await rodar(a);
      final eventos = r.map(
        (e) => e.getOrElse((_) => throw StateError('falha')),
      );
      expect(eventos.map((e) => e.runtimeType), [
        EventoRecuperacao,
        EventoParagrafo,
        EventoCitacoes,
        EventoAlerta,
        EventoFim,
      ]);
      final citacoes = eventos.whereType<EventoCitacoes>().single.citacoes;
      expect(citacoes.single.capitulo, '22');
      expect(citacoes.single.pagina, isNull);
      final fim = eventos.whereType<EventoFim>().single;
      expect(fim.nivelConfianca, NivelConfianca.semEvidencia);
      expect(fim.thoughtTokens, isNull);
      expect(fim.thinkingLevel, 'high');
      expect(
        eventos.whereType<EventoRecuperacao>().single.thinkingLevel,
        'low',
      );
      expect(fim.tempos.primeiroParagrafoValidado, 1400);
      expect(a.ultima!.uri.toString(), 'http://srv:8000/consulta');
      expect(a.ultima!.headers['X-API-Key'], 'chave');
      expect(a.ultima!.data, _corpo.paraJson());
    },
  );

  test(
    'evento erro vira falha e encerra; citação fantasma é FalhaCitacao',
    () async {
      final r = await rodar(
        _Adaptador(
          partes: [
            _sse('paragrafo', {
              'indice': 0,
              'texto': 'x',
              'chunkIds': ['c1'],
            }),
            _sse('erro', {'codigo': 'citacao_fantasma', 'mensagem': 'x'}),
            _sse('fim', {'nivelConfianca': 'alta', 'modelo': 'm'}),
          ],
        ),
      );
      expect(r, hasLength(2));
      expect(r.last.getLeft().toNullable(), isA<FalhaCitacao>());
    },
  );

  test('outros códigos de erro', () async {
    Future<Failure?> falha(String codigo) async {
      final r = await rodar(
        _Adaptador(
          partes: [
            _sse('erro', {'codigo': codigo, 'mensagem': 'm'}),
          ],
        ),
      );
      return r.single.getLeft().toNullable();
    }

    expect(await falha('falha_geracao'), isA<FalhaServidor>());
    expect(await falha('falha_recuperacao'), isA<FalhaServidor>());
    expect(await falha('resposta_invalida'), isA<FalhaContrato>());
    expect(await falha('inconsistencia_validador'), isA<FalhaCitacao>());
  });

  test('stream cortado antes do fim é falha de rede, não sucesso', () async {
    final r = await rodar(_Adaptador(partes: _feliz.sublist(0, 2)));
    expect(r.last.getLeft().toNullable(), isA<FalhaRede>());
  });

  test('evento desconhecido ou JSON ruim é FalhaContrato', () async {
    for (final partes in [
      [
        _sse('token', {'t': 'x'}),
      ],
      ['event: paragrafo\ndata: {nao-json\n\n'],
      [
        _sse('paragrafo', {'indice': 'zero'}),
      ],
    ]) {
      final r = await rodar(_Adaptador(partes: partes));
      expect(r.last.getLeft().toNullable(), isA<FalhaContrato>());
    }
  });

  test('HTTP 401, 429, 503 e erro de rede viram a falha certa', () async {
    Future<Failure?> falha(_Adaptador a) async =>
        (await rodar(a)).single.getLeft().toNullable();

    expect(await falha(_Adaptador(status: 401)), isA<FalhaContrato>());
    expect(await falha(_Adaptador(status: 429)), isA<FalhaCota>());
    expect(await falha(_Adaptador(status: 503)), isA<FalhaServidor>());
    expect(
      await falha(_Adaptador(erro: DioExceptionType.connectionError)),
      isA<FalhaRede>(),
    );
  });

  test('sem endereço configurado pede o ajuste', () async {
    final a = _Adaptador(partes: _feliz);
    final sem = RagRepositoryImpl(
      RagRemoteSource(Dio()..httpClientAdapter = a, const AppConfig()),
      _Configuracao(null),
    );
    final r2 = await sem.consultar(_corpo).toList();
    expect(r2.single.getLeft().toNullable(), isA<FalhaValidacao>());
  });
}
