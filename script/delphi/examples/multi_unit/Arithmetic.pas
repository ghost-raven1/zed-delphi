unit Arithmetic;

interface

type
  TCalculator = class
  private
    FLastResult: Integer;
  public
    function Calculate(LeftValue, RightValue: Integer): Integer;
    property LastResult: Integer read FLastResult;
  end;

function AddValues(LeftValue, RightValue: Integer): Integer;

implementation

function AddValues(LeftValue, RightValue: Integer): Integer;
begin
  Result := LeftValue + RightValue;
end;

function TCalculator.Calculate(LeftValue, RightValue: Integer): Integer;
begin
  FLastResult := AddValues(LeftValue, RightValue);
  Result := FLastResult;
end;

end.
