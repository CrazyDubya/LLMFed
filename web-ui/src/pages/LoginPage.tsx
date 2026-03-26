import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      if (isRegister) {
        await register(email, username, password);
      } else {
        await login(username, password);
      }
      navigate('/setup');
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f0f14]">
      <div className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-amber-400 mb-2">LLMFed</h1>
          <p className="text-gray-400">Wrestling World Simulator</p>
        </div>

        <div className="bg-[#1a1a24] rounded-lg p-6 border border-gray-800">
          <div className="flex mb-6">
            <button
              onClick={() => setIsRegister(false)}
              className={`flex-1 py-2 text-center rounded-l ${!isRegister ? 'bg-amber-600 text-white' : 'bg-gray-800 text-gray-400'}`}
            >
              Login
            </button>
            <button
              onClick={() => setIsRegister(true)}
              className={`flex-1 py-2 text-center rounded-r ${isRegister ? 'bg-amber-600 text-white' : 'bg-gray-800 text-gray-400'}`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
                required
              />
            )}
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full p-3 bg-[#0f0f14] border border-gray-700 rounded text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
              required
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              type="submit"
              className="w-full py-3 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded transition-colors"
            >
              {isRegister ? 'Create Account' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
