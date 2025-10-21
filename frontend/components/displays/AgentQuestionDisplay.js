// frontend/components/displays/AgentQuestionDisplay.js
import React, { useState, useEffect } from 'react';
import { Range, getTrackBackground } from 'react-range';
import InputField from '../ui/InputField';
import SingleSelectPillBoxField from '../ui/SingleSelectPillBoxField';
import MultiSelectPillBoxField from '../ui/MultiSelectPillBoxField';
import LiquidGlassButton from '../ui/LiquidGlassButton';
import LiquidGlassCard from '../ui/LiquidGlassCard';

const AgentQuestionDisplay = ({ question, onAnswer, isSubmitting }) => {
  const [localAnswer, setLocalAnswer] = useState(question.initialValue ?? '');
  const [localRange, setLocalRange] = useState(
    question.type === 'range_slider'
      ? question.initialValue ?? [question.minBoundary ?? 0, question.maxBoundary ?? 100]
      : [question.minBoundary ?? 0, question.maxBoundary ?? 100]
  );

  useEffect(() => {
    if (question.type === 'range_slider') {
      setLocalRange(question.initialValue ?? [question.minBoundary ?? 0, question.maxBoundary ?? 100]);
    } else {
      setLocalAnswer(question.initialValue ?? '');
    }
  }, [question]);

  const handleTextChange = (e) => setLocalAnswer(e.target.value);
  const handleNumberChange = (e) => setLocalAnswer(e.target.value === '' ? '' : Number(e.target.value));
  const handleDateChange = (e) => setLocalAnswer(e.target.value);
  const handleSingleSelectChange = (value) => setLocalAnswer(value);
  const handleMultiSelectChange = (values) => setLocalAnswer(values);
  const handleRangeChange = (values) => setLocalRange(values);

  const handleSubmit = () => {
    if (question.type === 'range_slider') {
      onAnswer({ min: localRange[0], max: localRange[1] });
    } else {
      onAnswer(localAnswer);
    }
  };

  const renderInputComponent = () => {
    switch (question.type) {
      case 'text':
        return (
          <InputField
            label=""
            type="text"
            value={localAnswer}
            onChange={handleTextChange}
            placeholder={question.placeholder ?? "Type your answer here..."}
            className="w-full"
            isTextArea={question.multiline ?? false}
          />
        );
      case 'number':
        return (
          <InputField
            label=""
            type="number"
            value={localAnswer}
            onChange={handleNumberChange}
            placeholder={question.placeholder ?? "Enter a number..."}
            className="w-full"
            min={question.min}
            max={question.max}
          />
        );
      case 'date':
        return (
          <InputField
            label=""
            type="date"
            value={localAnswer}
            onChange={handleDateChange}
            placeholder={question.placeholder ?? "Select a date..."}
            className="w-full"
          />
        );
      case 'single_select_pill':
        return (
          <SingleSelectPillBoxField
            label=""
            options={question.options ?? []}
            value={localAnswer}
            onChange={handleSingleSelectChange}
          />
        );
      case 'multi_select_pill':
        return (
          <MultiSelectPillBoxField
            label=""
            options={question.options ?? []}
            values={Array.isArray(localAnswer) ? localAnswer : []}
            onChange={handleMultiSelectChange}
          />
        );
      case 'range_slider':
        const minVal = question.minBoundary ?? 0;
        const maxVal = question.maxBoundary ?? 100;
        const stepVal = question.step ?? 1;
        return (
          <div className="flex flex-col items-center w-full px-4">
            <div className="flex justify-between w-full text-gray-300 text-sm mb-2">
              <span>{`Min: ${localRange[0].toFixed(0)}`}</span>
              <span>{`Max: ${localRange[1].toFixed(0)}`}</span>
            </div>
            <Range
              values={localRange}
              step={stepVal}
              min={minVal}
              max={maxVal}
              onChange={handleRangeChange}
              renderTrack={({ props, children }) => (
                <div
                  onMouseDown={props.onMouseDown}
                  onTouchStart={props.onTouchStart}
                  style={{
                    ...props.style,
                    height: '36px',
                    display: 'flex',
                    width: '100%',
                  }}
                >
                  <div
                    ref={props.ref}
                    style={{
                      height: '8px',
                      width: '100%',
                      borderRadius: '4px',
                      background: getTrackBackground({
                        values: localRange,
                        colors: ['#555', '#88F', '#555'],
                        min: minVal,
                        max: maxVal,
                      }),
                      alignSelf: 'center',
                    }}
                  >
                    {children}
                  </div>
                </div>
              )}
              renderThumb={({ props, isDragged }) => (
                <div
                  {...props}
                  style={{
                    ...props.style,
                    height: '20px',
                    width: '20px',
                    borderRadius: '50%',
                    backgroundColor: '#FFF',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    boxShadow: '0px 2px 6px rgba(0,0,0,0.3)',
                    outline: 'none',
                    border: '2px solid #88F'
                  }}
                >
                  <div
                    style={{
                      height: '8px',
                      width: '8px',
                      borderRadius: '50%',
                      backgroundColor: isDragged ? '#88F' : '#DDD',
                    }}
                  />
                </div>
              )}
            />
          </div>
        );
      case 'confirm':
        return (
          <SingleSelectPillBoxField
            label=""
            options={[{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }]}
            value={localAnswer}
            onChange={handleSingleSelectChange}
          />
        );
      case 'multiple_choice':
        return (
          <InputField
            type="text"
            placeholder={question.placeholder ?? "Please provide the purpose of your trip, destination, and your nationality."}
            value={localAnswer}
            onChange={handleTextChange}
            className="w-full"
          />
        );
      default:
        return (
          <div className="text-red-400">
            <p>Error: Unsupported question type from agent.</p>
            <p className="text-gray-50 text-lg font-semibold">{question.prompt}</p>
          </div>
        );
    }
  };

  const isAnswerValid = () => {
    switch (question.type) {
      case 'text':
      case 'multiple_choice':
      case 'date':
        return typeof localAnswer === 'string' && localAnswer.trim() !== '';
      case 'number':
        const numVal = Number(localAnswer);
        if (isNaN(numVal)) return false;
        if (question.min !== undefined && numVal < question.min) return false;
        if (question.max !== undefined && numVal > question.max) return false;
        return true;
      case 'single_select_pill':
        return localAnswer !== undefined && localAnswer !== null && localAnswer !== '';
      case 'multi_select_pill':
        return Array.isArray(localAnswer) && localAnswer.length > 0;
      case 'range_slider':
        return Array.isArray(localRange) && localRange.length === 2 && localRange[0] <= localRange[1];
      case 'confirm':
        return localAnswer === 'yes' || localAnswer === 'no';
      default:
        return false;
    }
  };

  return (
    <LiquidGlassCard className="p-6 space-y-4 max-w-2xl mx-auto mb-4">
      <p className="text-gray-50 text-lg font-semibold">{question.prompt}</p>
      <div className="mt-4">{renderInputComponent()}</div>
      <div className="flex justify-end mt-6">
        <LiquidGlassButton onClick={handleSubmit} disabled={isSubmitting || !isAnswerValid()}>
          {isSubmitting ? 'Submitting...' : 'Submit Answer'}
        </LiquidGlassButton>
      </div>
    </LiquidGlassCard>
  );
};

export default AgentQuestionDisplay;
