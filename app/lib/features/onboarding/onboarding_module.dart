import 'package:app/features/onboarding/data/repositories/onboarding_repository_impl.dart';
import 'package:app/features/onboarding/domain/repositories/onboarding_repository.dart';
import 'package:app/features/onboarding/domain/usecases/consultar_introducao_vista.dart';
import 'package:app/features/onboarding/domain/usecases/marcar_introducao_vista.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_cubit.dart';
import 'package:get_it/get_it.dart';
import 'package:hive_ce_flutter/hive_ce_flutter.dart';

/// Abre a caixa própria da introdução e registra as dependências do módulo.
///
/// Registro manual, à parte do `injectable`: o módulo é só de arquivos novos e
/// não altera `core/di/injection.dart` nem o código gerado. Chamar depois de
/// `configureDependencies()` (que inicializa o `hive_ce`).
Future<void> registrarOnboarding(GetIt getIt) async {
  if (getIt.isRegistered<IntroducaoCubit>()) return;
  final caixa = await Hive.openBox<dynamic>(nomeCaixaOnboarding);
  final OnboardingRepository repositorio = OnboardingRepositoryImpl(caixa);
  getIt.registerFactory<IntroducaoCubit>(
    () => IntroducaoCubit(
      ConsultarIntroducaoVista(repositorio),
      MarcarIntroducaoVista(repositorio),
    ),
  );
}
