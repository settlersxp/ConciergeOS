import { useState, useRef, useEffect } from 'react';
import { Button, Card } from './';
import { aiImprove } from '../../services/promptsApi';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface PromptImprovementChatProps {
  section: string;
  currentText: string;
  open: boolean;
  onClose: () => void;
  onApply: (improvedText: string) => void;
}

const SECTION_LABELS: Record<string, string> = {
  intention: 'Intention',
  restrictions: 'Restrictions',
  output_structure: 'Output Structure',
  user_prompt_template: 'User Prompt Template',
};

export default function PromptImprovementChat({
  section,
  currentText,
  open,
  onClose,
  onApply,
}: PromptImprovementChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [lastAssistantReply, setLastAssistantReply] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const sectionLabel = SECTION_LABELS[section] || section;

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open) {
      setMessages([]);
      setInput('');
      setLastAssistantReply(null);
      // Initial assistant message showing current text
      setMessages([
        {
          role: 'assistant',
          content: `Here's your current ${sectionLabel} section. Tell me how you'd like to improve it:

\`\`\`
${currentText}
\`\`\``,
        },
      ]);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open, currentText, sectionLabel]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || sending) return;

    const userMessage: ChatMessage = { role: 'user', content: input.trim() };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setSending(true);
    setLastAssistantReply(null);

    try {
      // Build conversation history without the initial assistant message
      // (the backend already knows the current text)
      const conversationHistory: ChatMessage[] = updatedMessages
        .filter((_, idx) => idx > 0) // Skip initial assistant message
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await aiImprove(section, currentText, conversationHistory);
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.improved_text,
      };
      setMessages([...updatedMessages, assistantMessage]);
      setLastAssistantReply(response.improved_text);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setMessages([
        ...updatedMessages,
        { role: 'assistant', content: `Error: ${errorMessage}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleApply = () => {
    if (lastAssistantReply) {
      onApply(lastAssistantReply);
    }
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card title={`AI Improve: ${sectionLabel}`} description="Chat with AI to iteratively improve this prompt section" className="w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Close button overlay */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-primary-500 hover:text-primary-700 dark:text-primary-400 dark:hover:text-white text-2xl leading-none"
        >
          &times;
        </button>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-2 py-4 space-y-4 min-h-0">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-surface-200 dark:bg-primary-700 text-primary-900 dark:text-white'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-lg px-4 py-3 bg-surface-200 dark:bg-primary-700 text-primary-500 dark:text-primary-400 text-sm">
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-surface-200 dark:border-primary-700 px-6 py-4">
          <div className="flex gap-2 mb-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe how you want to improve this section..."
              disabled={sending}
              className="flex-1 rounded-md border border-surface-300 dark:border-primary-600 bg-surface-50 dark:bg-primary-900 px-3 py-2 text-sm text-primary-900 dark:text-white placeholder-primary-400 dark:placeholder-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
            />
            <Button onClick={handleSend} disabled={!input.trim() || sending} variant="primary">
              Send
            </Button>
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Cancel</Button>
            <Button onClick={handleApply} disabled={!lastAssistantReply} variant="primary">
              Apply Improvement
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}