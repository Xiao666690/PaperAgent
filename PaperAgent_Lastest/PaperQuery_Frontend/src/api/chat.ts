import api, { authFetch } from "@/api/api";

import { parsePack2 } from "@/utils/parsePack";

export const uploadFile = async (
  file: File,
  options: { addToLibrary?: boolean; knowledgeID?: string } = {},
) => {
  try {
    const formData = new FormData();
    formData.append("documentFile", file);
    formData.append("addToLibrary", String(Boolean(options.addToLibrary)));
    if (options.knowledgeID) {
      formData.append("knowledgeID", options.knowledgeID);
    }
    const resp = await api.post(
      '/document/multi_file_chat_upload',
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 60000,
      }
    );
    return resp.data.data;
  } catch (error) {
    console.log(error);
    throw error;
  }
};

export const getAnswerStream = async (
  question: string,
  context: string,
  uid: Array<string>,
  model: string = "deepseek"
) => {
  try {
    const res = await authFetch('/chat/mulit_file_chat_generate_flow', {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify({
        question: question,
        context: context,
        uid: uid,
        model: model,
      }),
    });
    if (!res.ok) {
      throw new Error(`请求失败：HTTP ${res.status}`);
    }
    if (!res.body) {
      throw new Error("Network response was not ok");
    }
    const reader = res.body?.getReader();
    const decoder = new TextDecoder("utf-8");

    return new ReadableStream({
      async start(controller) {
        function push() {
          // "done" is a Boolean and value a "Uint8Array"
          reader.read().then(({ done, value }) => {
            // If there is no more data to read
            if (done) {
              // console.log("done", done);
              controller.close();
              return;
            }
            const chunk = parsePack2(
              decoder.decode(value, { stream: true })
            ) as any;
            // Get the data and send it to the browser via the controller
            controller.enqueue(chunk);
            // Check chunks by logging to the console
            push();
          });
        }
        push();
      },
    });
  } catch (error: any) {
    console.error(
      "Error:",
      error.response ? error.response.data : error.message
    );
    throw error;
  }
};

// 更新记忆力
export const updateMemory = async (
  question: string,
  context: string,
  answer: string
) => {
  try {
    const data = {
      question: question,
      context: context,
      answer: answer,
    };
    const resp = await api.post('/chat/summarize', data, { timeout: 60000 });
    return resp.data.data;
  } catch (error) {
    console.log(error);
  }
};
