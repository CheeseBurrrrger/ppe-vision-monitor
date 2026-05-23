import { useNavigate } from "react-router-dom";

export default function Login() {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#E5DCC5]">
        <div className="bg-[#F5EDE0] rounded-2xl w-full max-w-lg p-10 shadow-sm">

            <div className="pb-6 mb-6 border-b border-gray-400">
            <h1 className="text-2xl font-bold text-gray-900">VisionGuard</h1>
            <p className="text-sm text-gray-500 mt-1">K3 Monitoring</p>
            <p className="text-sm text-gray-500">PT. Epson Indonesia</p>
            </div>

            <h2 className="text-5xl font-light text-gray-900 mb-8">Login</h2>

            <div className="space-y-5">
            <div>
                <label className="block text-sm text-gray-700 mb-1">Username</label>
                <input
                type="text"
                className="w-full border border-red-400 rounded-lg px-4 py-3 bg-[#F5EDE0] outline-none focus:ring-2 focus:ring-red-400"
                />
            </div>

            <div>
                <label className="block text-sm text-gray-700 mb-1">Password</label>
                <input
                type="password"
                className="w-full border border-red-200 rounded-lg px-4 py-3 bg-[#F5EDE0] outline-none focus:ring-2 focus:ring-red-400"
                />
            </div>

            <button
                onClick={() => navigate("/dashboard")}
                className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg transition">
                Login
            </button>

            <div className="text-right">
                <span className="text-sm text-gray-400 cursor-pointer hover:underline">
                Forgot Password?
                </span>
            </div>
            </div>

            <p className="text-xs text-gray-400 mt-8">©team sembilan</p>
        </div>
        </div>
    );
}