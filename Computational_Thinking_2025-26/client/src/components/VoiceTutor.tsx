import React from "react";
import { motion, AnimatePresence } from "motion/react";

interface VoiceTutorProps {
  isOpen: boolean;
  onClose: () => void;
  status: string;
  isRecording: boolean;
  userBars: number[];
  aiLevel: number;
  isMuted: boolean;
  onToggleMute: () => void;
  onReconnect: () => void; // Added prop
}

const VoiceTutor: React.FC<VoiceTutorProps> = ({ 
  isOpen, onClose, status, isRecording, userBars, aiLevel, isMuted, onToggleMute, onReconnect 
}) => {
  
  const isAiSpeaking = aiLevel > 0.04;
  const isUserSpeaking = userBars.some((b) => b > 25);
  const isDisconnected = status === "Disconnected";

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="voice-modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
        >
          <div className="voice-modal-container">
            {/* Header / Close Button */}
            <div className="voice-modal-header">
              <div className="voice-brand">
                <span className="logo-icon">∑</span>
                <span>Prism Live Voice</span>
              </div>
              <button
                type="button"
                className="voice-close-btn"
                onClick={onClose}
                aria-label="Close voice tutor"
              >
                ✕
              </button>
            </div>

            {/* Center: Fluid AI Voice Orb */}
            <div className="voice-fluid-stage">
              <motion.div
                className="voice-fluid-glow"
                animate={{
                  scale: isAiSpeaking ? 1 + aiLevel * 0.9 : 1,
                  opacity: isAiSpeaking ? 0.85 : 0.45,
                }}
                transition={{ type: "spring", stiffness: 180, damping: 20 }}
              />

              <motion.div
                className="voice-fluid-core"
                animate={{
                  scale: isAiSpeaking ? 1 + aiLevel * 0.6 : [1, 1.05, 1],
                  rotate: isAiSpeaking ? [0, 90, 180, 270, 360] : 0,
                  borderRadius: isAiSpeaking
                    ? [
                        "60% 40% 30% 70% / 60% 30% 70% 40%",
                        "40% 60% 70% 30% / 50% 60% 30% 60%",
                        "60% 40% 30% 70% / 60% 30% 70% 40%",
                      ]
                    : "50%",
                }}
                transition={{
                  scale: { type: "spring", stiffness: 220, damping: 15 },
                  rotate: { duration: 8, repeat: Infinity, ease: "linear" },
                  borderRadius: { duration: 3, repeat: Infinity, ease: "easeInOut" },
                }}
              >
                <div className="voice-fluid-inner" style={{ filter: isDisconnected ? 'grayscale(100%)' : 'blur(4px)' }} />
              </motion.div>

              {/* Dynamic Status Pill */}
              <div className="voice-status-pill">
                <span 
                  className={`status-indicator-dot ${isRecording ? "active" : ""}`} 
                  style={isDisconnected ? { background: '#ef4444', boxShadow: '0 0 8px #ef4444' } : {}}
                />
                <span>
                  {status === "Connecting..."
                    ? "Connecting..."
                    : isDisconnected
                    ? "Connection idle — timed out"
                    : isAiSpeaking
                    ? "AI is speaking"
                    : isUserSpeaking
                    ? "Listening to you"
                    : "Ready · Speak anytime"}
                </span>
              </div>
            </div>

            {/* Bottom: User Voice Equalizer Bars */}
            <div className="voice-user-container">
              <div className="voice-user-bars" aria-label="Microphone volume bars" style={{ opacity: isDisconnected ? 0.2 : 1 }}>
                {userBars.map((height, idx) => (
                  <motion.div
                    key={idx}
                    className="voice-bar"
                    animate={{ height: `${height}px` }}
                    transition={{ type: "spring", stiffness: 450, damping: 25 }}
                  />
                ))}
              </div>
              <span className="voice-user-label">Your Voice</span>

              {/* Dynamic Action Buttons */}
              <div className="voice-actions" style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', alignItems: 'center' }}>
                
                {isDisconnected ? (
                  <button 
                    type="button" 
                    className="voice-end-btn" 
                    onClick={onReconnect}
                    style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', borderColor: 'rgba(59, 130, 246, 0.3)' }}
                  >
                    Reconnect to AI
                  </button>
                ) : (
                  <button type="button" className="voice-end-btn" onClick={onClose}>
                    End Call
                  </button>
                )}

                {!isDisconnected && (
                  <button 
                    type="button" 
                    className={`voice-mute-btn ${isMuted ? 'muted' : ''}`} 
                    onClick={onToggleMute}
                    aria-label={isMuted ? "Unmute" : "Mute"}
                    title={isMuted ? "Unmute" : "Mute"}
                  >
                    {isMuted ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="1" y1="1" x2="23" y2="23"></line><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"></path><line x1="12" x2="12" y1="19" y2="22"></line></svg>
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" x2="12" y1="19" y2="22"></line></svg>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default VoiceTutor;