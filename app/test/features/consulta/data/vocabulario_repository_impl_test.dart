import 'dart:convert';
import 'dart:io';

import 'package:app/core/config/app_config.dart';
import 'package:app/core/error/failures.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/consulta/data/repositories/vocabulario_repository_impl.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive_ce.dart';

const Map<String, Object> _json = {
  'versao': 'abc123',
  'especies': ['canino', 'felino'],
  'farmacos': [
    {
      'nome': 'meloxicam',
      'sinonimos': ['Metacam'],
    },
  ],
  'comorbidades': [
    {'chave': 'epilepsia', 'rotulo': 'epilepsia'},
  ],
};

class _Adaptador implements HttpClientAdapter {
  new({this.corpo, this.status = 200, this.erro});

  final Object? corpo;
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

void main() {
  late Directory dir;
  late Box<dynamic> caixa;

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('vocab_test');
    Hive.init(dir.path);
    caixa = await Hive.openBox<dynamic>('configuracao');
  });

  tearDown(() async {
    await Hive.close();
    dir.deleteSync(recursive: true);
  });

  VocabularioRepositoryImpl repo(_Adaptador a) => VocabularioRepositoryImpl(
    Dio()..httpClientAdapter = a,
    caixa,
    const AppConfig(clientApiKey: 'chave'),
    _Configuracao('http://srv:8000/'),
  );

  test('busca no servidor com X-API-Key, interpreta e guarda cópia', () async {
    final a = _Adaptador(corpo: _json);
    final r = await repo(a).obter();
    final v = r.getOrElse((_) => throw StateError('falha'));
    expect(v.versao, 'abc123');
    expect(v.farmacos.single.sinonimos, ['Metacam']);
    expect(v.comorbidades.single.chave, 'epilepsia');
    expect(a.ultima!.uri.toString(), 'http://srv:8000/vocabulario');
    expect(a.ultima!.headers['X-API-Key'], 'chave');
    expect(caixa.get(chaveVocabulario), isA<String>());
  });

  test('sem rede, serve a cópia local', () async {
    await repo(_Adaptador(corpo: _json)).obter();
    final r = await repo(_Adaptador(erro: DioExceptionType.connectionError))
        .obter();
    expect(r.isRight(), isTrue);
  });

  test('sem rede e sem cópia, devolve a falha de rede', () async {
    final r = await repo(_Adaptador(erro: DioExceptionType.connectionError))
        .obter();
    expect(r.getLeft().toNullable(), isA<FalhaRede>());
  });

  test('401 sem cópia vira FalhaContrato', () async {
    final r = await repo(_Adaptador(corpo: {'detail': 'x'}, status: 401))
        .obter();
    expect(r.getLeft().toNullable(), isA<FalhaContrato>());
  });

  test('JSON fora do contrato não é guardado', () async {
    final r = await repo(_Adaptador(corpo: {'versao': 1})).obter();
    expect(r.getLeft().toNullable(), isA<FalhaContrato>());
    expect(caixa.get(chaveVocabulario), isNull);
  });

  test('sem endereço e sem cópia pede o ajuste', () async {
    final a = _Adaptador(corpo: _json);
    final r = await VocabularioRepositoryImpl(
      Dio()..httpClientAdapter = a,
      caixa,
      const AppConfig(),
      _Configuracao(null),
    ).obter();
    expect(r.getLeft().toNullable(), isA<FalhaValidacao>());
    expect(a.ultima, isNull);
  });
}
