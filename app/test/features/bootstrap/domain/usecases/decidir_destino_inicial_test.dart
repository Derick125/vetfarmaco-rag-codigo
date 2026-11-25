import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/bootstrap/domain/usecases/decidir_destino_inicial.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockConfiguracaoRepository extends Mock
    implements ConfiguracaoRepository;

void main() {
  late _MockConfiguracaoRepository repositorio;
  late DecidirDestinoInicial decidirDestinoInicial;

  setUp(() {
    repositorio = _MockConfiguracaoRepository();
    decidirDestinoInicial = DecidirDestinoInicial(repositorio);
  });

  test('retorna falhaConfig quando não há endereço de back-end', () async {
    when(repositorio.enderecoBackend).thenAnswer((_) async => null);

    final destino = await decidirDestinoInicial();

    expect(destino, DestinoInicial.falhaConfig);
    verifyNever(repositorio.termoAceitoEm);
  });

  test('retorna falhaConfig quando o endereço está vazio', () async {
    when(repositorio.enderecoBackend).thenAnswer((_) async => '');

    final destino = await decidirDestinoInicial();

    expect(destino, DestinoInicial.falhaConfig);
  });

  test('retorna termo quando o termo de uso ainda não foi aceito', () async {
    when(repositorio.enderecoBackend)
        .thenAnswer((_) async => 'https://api.exemplo.com');
    when(repositorio.termoAceitoEm).thenAnswer((_) async => null);

    final destino = await decidirDestinoInicial();

    expect(destino, DestinoInicial.termo);
  });

  test('retorna consulta quando o termo já foi aceito', () async {
    when(repositorio.enderecoBackend)
        .thenAnswer((_) async => 'https://api.exemplo.com');
    when(repositorio.termoAceitoEm).thenAnswer((_) async => DateTime(2026));

    final destino = await decidirDestinoInicial();

    expect(destino, DestinoInicial.consulta);
  });
}
