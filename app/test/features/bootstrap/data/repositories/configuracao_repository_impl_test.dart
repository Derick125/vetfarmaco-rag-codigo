import 'dart:io';

import 'package:app/core/config/app_config.dart';
import 'package:app/features/bootstrap/data/repositories/configuracao_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive_ce.dart';

void main() {
  late Directory dir;
  late Box<dynamic> caixa;

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('config_test');
    Hive.init(dir.path);
    caixa = await Hive.openBox<dynamic>('configuracao');
  });

  tearDown(() async {
    await Hive.close();
    dir.deleteSync(recursive: true);
  });

  test('sem override nem --dart-define, endereço é null', () async {
    final repo = ConfiguracaoRepositoryImpl(caixa, const AppConfig());
    expect(await repo.enderecoBackend(), isNull);
  });

  test('usa o endereço do --dart-define quando não há override', () async {
    final repo = ConfiguracaoRepositoryImpl(
      caixa,
      const AppConfig(apiBaseUrl: 'http://10.0.2.2:8000'),
    );
    expect(await repo.enderecoBackend(), 'http://10.0.2.2:8000');
  });

  test('o endereço salvo em ajustes sobrepõe o --dart-define', () async {
    await caixa.put(chaveEnderecoBackend, ' http://192.168.0.5:8000 ');
    final repo = ConfiguracaoRepositoryImpl(
      caixa,
      const AppConfig(apiBaseUrl: 'http://10.0.2.2:8000'),
    );
    expect(await repo.enderecoBackend(), 'http://192.168.0.5:8000');
  });

  test('override vazio cai no --dart-define', () async {
    await caixa.put(chaveEnderecoBackend, '  ');
    final repo = ConfiguracaoRepositoryImpl(
      caixa,
      const AppConfig(apiBaseUrl: 'http://x'),
    );
    expect(await repo.enderecoBackend(), 'http://x');
  });

  test('termoAceitoEm lê a data gravada', () async {
    final repo = ConfiguracaoRepositoryImpl(caixa, const AppConfig());
    expect(await repo.termoAceitoEm(), isNull);
    final t = DateTime(2026, 10, 2);
    await caixa.put(chaveTermoAceitoEm, t);
    expect(await repo.termoAceitoEm(), t);
  });
}
