import 'package:app/core/error/failures.dart';
import 'package:app/features/onboarding/domain/repositories/onboarding_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Informa se a introdução de primeiro uso já foi vista.
class ConsultarIntroducaoVista {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final OnboardingRepository _repositorio;

  /// `Right(false)` na primeira vez.
  Future<Either<Failure, bool>> call() => _repositorio.introducaoVista();
}
