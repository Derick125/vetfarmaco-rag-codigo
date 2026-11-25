import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/features/termo/data/repositories/termo_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';

void main() {
  late Directory dir;
  late Box<dynamic> caixa;
  final instante = DateTime(2026, 10, 2, 9);

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('termo_test');
    Hive.init(dir.path);
    caixa = await Hive.openBox<dynamic>('configuracao');
  });

  tearDown(() async {
    await Hive.close();
    dir.deleteSync(recursive: true);
  });

  test('sem aceite devolve Right(null)', () async {
    expect(
      await TermoRepositoryImpl(caixa).aceitoEm(),
      const Right<Failure, DateTime?>(null),
    );
  });

  test('registra e relê o aceite', () async {
    final repo = TermoRepositoryImpl(caixa);
    expect(
      await repo.registrarAceite(instante),
      const Right<Failure, Unit>(unit),
    );
    expect(await repo.aceitoEm(), Right<Failure, DateTime?>(instante));
  });

  test('caixa fechada vira FalhaCache, sem lançar', () async {
    final repo = TermoRepositoryImpl(caixa);
    await caixa.close();
    expect((await repo.aceitoEm()).isLeft(), isTrue);
    final r = await repo.registrarAceite(instante);
    expect(r.getLeft().toNullable(), isA<FalhaCache>());
  });
}
