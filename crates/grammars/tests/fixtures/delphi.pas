unit Demo.Model;

interface

uses System.SysUtils, System.Generics.Collections;

type
  TBox<T> = class
  private
    FValue: T;
  public
    constructor Create(const AValue: T);
    property Value: T read FValue write FValue;
  end;

  TCounter = record
    Value: Integer;
    procedure Increment;
  end;

implementation

constructor TBox<T>.Create(const AValue: T);
begin
  FValue := AValue;
end;

procedure TCounter.Increment;
begin
  try
    Inc(Value);
  finally
    WriteLn('It''s Delphi');
  end;
end;

end.
