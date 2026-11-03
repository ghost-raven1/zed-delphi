unit MainForm;

{$mode objfpc}{$H+}

interface

uses
  Classes, SysUtils, Forms, Controls, StdCtrls, ExtCtrls;

type
  TDemoForm = class(TForm)
    CalculateButton: TButton;
    CloseButton: TButton;
    ResultLabel: TLabel;
    SmokeTimer: TTimer;
    procedure CalculateButtonClick(Sender: TObject);
    procedure CloseButtonClick(Sender: TObject);
    procedure FormShow(Sender: TObject);
    procedure SmokeTimerTimer(Sender: TObject);
  private
    FCalculated: Boolean;
  end;

var
  DemoForm: TDemoForm;

implementation

{$R *.lfm}

procedure TDemoForm.CalculateButtonClick(Sender: TObject);
var
  LeftValue, RightValue, TotalValue: Integer;
begin
  LeftValue := 20;
  RightValue := 22;
  TotalValue := LeftValue + RightValue; // LCL_BREAKPOINT
  ResultLabel.Caption := 'Result: ' + IntToStr(TotalValue); // LCL_AFTER_STEP
  FCalculated := True;
  WriteLn('LCL_RESULT=', TotalValue);
  Flush(Output);
end;

procedure TDemoForm.CloseButtonClick(Sender: TObject);
begin
  Close;
end;

procedure TDemoForm.FormShow(Sender: TObject);
begin
  WriteLn('LCL_SHOWN');
  Flush(Output);
  SmokeTimer.Enabled := ParamStr(1) = '--smoke-test';
end;

procedure TDemoForm.SmokeTimerTimer(Sender: TObject);
begin
  SmokeTimer.Enabled := False;
  if not FCalculated then
  begin
    CalculateButton.Click;
    SmokeTimer.Interval := 2000;
    SmokeTimer.Enabled := True;
  end
  else
    CloseButton.Click;
end;

end.
