import 'dart:convert';
import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/core/network/dio_failure_mapper.dart';
import 'package:app/features/ajustes/data/repositories/ajustes_repository_impl.dart';
import 'package:app/features/bootstrap/data/repositories/configuracao_repository_impl.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';

/// Adaptador que responde com um status fixo ou lança [DioException].
class _Adaptador implements HttpClientAdapter {
  new({this.status, this.erro});

  final int? status;
  final DioExceptionType? erro;
  String? ultimaUrl;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    ultimaUrl = options.uri.toString();
    if (erro != null) {
      throw DioException(requestOptions: options, type: erro!);
    }
    return ResponseBody.fromString(
      jsonEncode({'status': 'ok'}),
      status!,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  late Directory dir;
  late Box<dynamic> caixa;

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('ajustes_test');
    Hive.init(dir.path);
    caixa = await Hive.openBox<dynamic>('configuracao');
  });

  tearDown(() async {
    await Hive.close();
    dir.deleteSync(recursive: true);
  });

  AjustesRepositoryImpl repo(_Adaptador a) =>
      AjustesRepositoryImpl(caixa, Dio()..httpClientAdapter = a);

  test('salvarEndereco grava na chave lida pela configuração', () async {
    final r = await repo(_Adaptador(status: 200)).salvarEndereco('http://x');
    expect(r, const Right<Failure, Unit>(unit));
    expect(caixa.get(chaveEnderecoBackend), 'http://x');
  });

  test('salvarEndereco com caixa fechada vira FalhaCache', () async {
    final a = repo(_Adaptador(status: 200));
    await caixa.close();
    final r = await a.salvarEndereco('http://x');
    expect(r.getLeft().toNullable(), isA<FalhaCache>());
  });

  test('testarBackend chama GET /health e aceita 200', () async {
    final a = _Adaptador(status: 200);
    final r = await repo(a).testarBackend('http://x:8000');
    expect(r, const Right<Failure, Unit>(unit));
    expect(a.ultimaUrl, 'http://x:8000/health');
  });

  test('testarBackend: 500 vira FalhaServidor', () async {
    final r = await repo(_Adaptador(status: 500)).testarBackend('http://x');
    expect(r.getLeft().toNullable(), isA<FalhaServidor>());
  });

  test('testarBackend: sem conexão vira FalhaRede', () async {
    final r = await repo(_Adaptador(erro: DioExceptionType.connectionError))
        .testarBackend('http://x');
    expect(r.getLeft().toNullable(), isA<FalhaRede>());
  });

  test('testarBackend: timeout vira FalhaTempo', () async {
    final r = await repo(_Adaptador(erro: DioExceptionType.connectionTimeout))
        .testarBackend('http://x');
    expect(r.getLeft().toNullable(), isA<FalhaTempo>());
  });

  group('falhaDeStatus', () {
    test('429 é cota', () => expect(falhaDeStatus(429), isA<FalhaCota>()));
    test(
      '503 é servidor',
      () => expect(falhaDeStatus(503), isA<FalhaServidor>()),
    );
    test('401 é contrato (chave)', () {
      expect(falhaDeStatus(401), isA<FalhaContrato>());
    });
    test(
      '404 é contrato',
      () => expect(falhaDeStatus(404), isA<FalhaContrato>()),
    );
  });

  test('falhaDeDio cobre cancelamento e certificado', () {
    for (final tipo in [
      DioExceptionType.cancel,
      DioExceptionType.badCertificate,
      DioExceptionType.unknown,
    ]) {
      final e = DioException(requestOptions: RequestOptions(), type: tipo);
      expect(falhaDeDio(e), isA<FalhaRede>());
    }
    final bad = DioException(
      requestOptions: RequestOptions(),
      type: DioExceptionType.badResponse,
      response: Response(requestOptions: RequestOptions(), statusCode: 429),
    );
    expect(falhaDeDio(bad), isA<FalhaCota>());
  });
}
