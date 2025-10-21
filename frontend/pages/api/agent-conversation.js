// frontend/pages/api/agent-conversation.js

/**
 * This Next.js API route acts as a proxy, forwarding frontend requests to the Python FastAPI AI service.
 * It now handles a more comprehensive session state.
 */

const API_VERSION = 'v1';
const API_PLANNING_ENDPOINT = `/api/${API_VERSION}/plan/next-step`;

export default async function handler(req, res) {
    console.log('--- Agent Conversation API route is being hit! ---');
    console.log('Received request method:', req.method);

    if (req.method !== 'POST') {
        res.setHeader('Allow', ['POST']);
        return res.status(405).end(`Method ${req.method} Not Allowed`);
    }

    try {
        const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_BASE_URL;
        if (!backendBaseUrl) {
            console.error('Environment variable NEXT_PUBLIC_BACKEND_BASE_URL is not set.');
            return res.status(500).json({
                error: "Backend URL is not configured. Please check your .env.local file."
            });
        }
        const backendUrl = `${backendBaseUrl}${API_PLANNING_ENDPOINT}`;

        console.log('Constructed backend URL:', backendUrl);
        console.log('Request body to backend:', req.body);

        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(req.body),
        });

        // 检查响应头，确保它是 JSON 类型
        const contentType = response.headers.get('content-type');
        const isJson = contentType && contentType.includes('application/json');

        if (response.ok && isJson) {
            const data = await response.json();
            console.log('Backend parsed JSON data:', data);
            return res.status(200).json(data);
        } else if (isJson) {
            // 如果状态码不是200但内容是JSON，则解析错误信息
            const errorData = await response.json();
            console.error("Backend returned JSON error:", errorData);
            return res.status(response.status).json(errorData);
        } else {
            // 这是最关键的部分：处理非JSON响应，如"hi"或HTML错误页面
            const errorText = await response.text();
            console.error("Backend returned non-JSON response:", errorText);
            
            // 返回一个结构化的JSON错误，确保前端永远不会收到非JSON数据
            return res.status(response.status || 500).json({ 
                agent_response: {
                    message_type: 'text',
                    content: {
                        prompt: `Received an unexpected non-JSON response from the planning service. Raw response: ${errorText.substring(0, 100)}`
                    }
                },
                updated_session_state: req.body.session_state
            });
        }
    } catch (error) {
        console.error("Error communicating with AI Agent backend:", error);
        res.status(500).json({ 
            agent_response: {
                message_type: 'text',
                content: {
                    prompt: `I am unable to connect to the planning service right now. Please try again in a moment. Debug Info: ${error.message}`
                }
            },
            updated_session_state: req.body.session_state
        });
    }
}