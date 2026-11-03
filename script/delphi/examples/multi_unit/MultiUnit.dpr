program MultiUnit;

uses
  Arithmetic in 'Arithmetic.pas';

var
  Calculator: TCalculator;
  Answer: Integer;
begin
  Calculator := TCalculator.Create;
  try
    Answer := Calculator.Calculate(20, 22);
    WriteLn(Answer);
    if (Answer <> 42) or (Calculator.LastResult <> 42) then
      Halt(1);
  finally
    Calculator.Free;
  end;
end.
