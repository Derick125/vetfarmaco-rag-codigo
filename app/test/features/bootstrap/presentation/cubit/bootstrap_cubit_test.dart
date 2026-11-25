import 'package:app/features/bootstrap/domain/usecases/decidir_destino_inicial.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_cubit.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockDecidirDestinoInicial extends Mock implements DecidirDestinoInicial;

void main() {
  late _MockDecidirDestinoInicial decidirDestinoInicial;

  setUp(() {
    decidirDestinoInicial = _MockDecidirDestinoInicial();
  });

  blocTest<BootstrapCubit, BootstrapState>(
    'emite [ParaTermo] quando o termo de uso não foi aceito',
    setUp: () =>
        when(decidirDestinoInicial.call)
            .thenAnswer((_) async => DestinoInicial.termo),
    build: () => BootstrapCubit(decidirDestinoInicial),
    act: (cubit) => cubit.iniciar(),
    expect: () => const [ParaTermo()],
  );

  blocTest<BootstrapCubit, BootstrapState>(
    'emite [ParaConsulta] quando o app já está pronto para uso',
    setUp: () =>
        when(decidirDestinoInicial.call)
            .thenAnswer((_) async => DestinoInicial.consulta),
    build: () => BootstrapCubit(decidirDestinoInicial),
    act: (cubit) => cubit.iniciar(),
    expect: () => const [ParaConsulta()],
  );

  blocTest<BootstrapCubit, BootstrapState>(
    'emite [FalhaConfig] quando o endereço do back-end está ausente',
    setUp: () =>
        when(decidirDestinoInicial.call)
            .thenAnswer((_) async => DestinoInicial.falhaConfig),
    build: () => BootstrapCubit(decidirDestinoInicial),
    act: (cubit) => cubit.iniciar(),
    expect: () => const [FalhaConfig()],
  );
}
