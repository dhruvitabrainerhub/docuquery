# from django.shortcuts import render

# # Create your views here.
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from .models import Documents, ChatSession, ChatMessage
# from .serializers import DocumentUploadSerializer
# from .services.parser import extract_text
# from .services.chunker import create
# from .services.embeddings import vector_db
# from .services.rag_pipeline import llm
# from rest_framework.parsers import MultiPartParser,FormParser
# from rest_framework import generics
# from langchain.retrievers.multi_query import MultiQueryRetriever
# from collections import defaultdict
# import re

# # class UploadDocumentView(APIView):
# #     parser_classes = [MultiPartParser,FormParser]

# #     def post(self,request):
# #         serializer = DocumentUploadSerializer(
# #             data = request.data
# #         )
# #         if serializer.is_valid():
# #             document = serializer.save()

# #         return response(
# #             {
# #                 'id':document.id,
# #                 'message': 'upload successfully'
# #             })

# #         return Response(serializer.errors, status=400)
        

# class UploadDocumentView(generics.CreateAPIView):
#     queryset = Documents.objects.all()
#     serializer_class = DocumentUploadSerializer

# class ProcessDocumentView(APIView):
#     def post(self,request,document_id):
#         document = Documents.objects.get(
#             id = document_id
#         )
#         print("DOCUMENT:",document.id)
#         print("FILE:",document.file)

#         # text = extract_text(
#         #     document.file.path
#         # )
#         pages = extract_text(
#             document.file.path
#         )
#         all_chunks = []
#         all_metadatas = []

#         for page_data in pages:
#             page_number = page_data['page']
#             text = page_data['text']

#             print("TEXT LENGTH:", len(text))
#             print(text[:500])

#             chunks = create(text)
#             print('Chunks:',len(chunks))
#             print(chunks[:2])

#             for idx,chunk in enumerate(chunks):
#                 all_chunks.append(chunk)
#                 all_metadatas.append(
#                     {
#                         'document_id':document.id,
#                         'source':document.file.name,
#                         'page':page_number,
#                         'chunk_id':idx
#                      }
#                 )
#                 if not chunks:
#                     return Response(
#                         {
#                             'error': 'No text chunks created from documents'
#                         },
#                         status = 400
#                     )      

#         vector_db.add_texts(
#             texts = all_chunks,
#             metadatas = all_metadatas
#         )

#         document.processed = True
#         document.save()

#         return Response(
#             {
#                 'messages': 'document processed'
#             }
#         )

# class CreateSessionView(APIView):
#     def post(self ,request):
#         session = ChatSession.objects.create(
#             title = 'New Chat'
#         )

#         return Response(
#             {
#                 'session_id':session.id,
#                 'title': session.title
#             }
#         )

# class ChatView(APIView):
#     def post(self,request,session_id):
#         question = request.data.get('question')

#         if not question:
#             return Response(
#                 {'error' : 'question is required'},
#                 status = 400
#             )
#         try:
#             session = ChatSession.objects.get(
#                 id = session_id
#             )
#         except ChatSession.DoesNotExist:
#             return Response(
#                 {'error':'session not found'},
#                 status = 404
#             )
            
#         #get previous chat history
#         history_message = ChatMessage.objects.filter(
#             session = session
#         ).order_by('created_at')

#         history = ""
#         for msg in history_message:
#             history += f"{msg.role} : {msg.context}\n"

#         # Retrieve relevant docs    
#         retriever = vector_db.as_retriever(
#             search_kwargs = {'k':8}
#         )

#         docs = retriever.invoke(question)

#         #context = '\n\n'.join(
#         #     doc.page_content
#         #     for doc in docs
#         # )

#         context = '\n\n'.join(
#             [
#                 f"[Page {doc.metadata['page']}]\n{doc.page_content}"
#                 for doc in docs 
#             ]
#         #     doc.page_content
#         #     for doc in docs
#         )


#         prompt = f"""
#         you are a helpful RAG assistant.
#         Answer only from context.
#         For every statement cite page number like [Page X].
        
#         at the end return:
#         PAGES_USED : comma seprated page numbers
#         previous conversation:{history}        

#         document Context : {context}

#         Question : {question}

#         Rules:
#         1 Use document context first.
#         2. Use conversation history to resolve references like:
#             -it
#             -they
#             -that event
#             -this topic
#         3. If answer is not present in context, say:
#         "I couldn't find that information."
#         4. do not mention page inside the answer text itself.
#         5. only list a page in PAGE_USED if you actually used information from 
#         the page's content to construct the answer.Do not list every page that
#         provided in the context, only the ones whoes content you relied on.
#         6. at the very end of your response, on its own line,return
#         exactly in this format(no extra spaces, no extra words):
#         PAGE_USED : comma, seprated, page, numbers
#         Example:
#         the answer goes there.
#         PAGES_USED : 3,7
#         """

#         answer = llm.invoke(prompt)

#         #save use message
#         ChatMessage.objects.create(
#             session = session,
#             role = 'user',
#             context = question
#         )

#         #save assistant message
#         ChatMessage.objects.create(
#             session = session,
#             role = 'assistant',
#             context = answer.content
#         )
#         # sources = list({
#         #     doc.metadata.get("source","")
#         #     for doc in docs
#         # })

#         raw_answer = answer.content
#         print('='*50)
#         print(raw_answer)
#         print('='*50)

#         answer_text = raw_answer
#         used_pages = []

#         match = re.search(
#             r'PAGES_USED\s*:\s*(.*)',
#             raw_answer,
#             re.IGNORECASE
#         )
#         if match:
#             answer_text = raw_answer[:match.start()].strip()
#             pages_text = match.group(1)
#         else:
#             answer_text = raw_answer.strip()
#             pages_text = ""
#             # if 'PAGES_USED:' in raw_answer:
#             #     answer_text,pages_text = raw_answer.split('PAGES_USED:',1)
#             # else:
#             #     answer_text = raw_answer
#             #     pages_text = ""
            
#             for p in pages_text.split(","):
#                 p = p.strip()
#                 if p.isdigit():
#                     used_pages.append(int(p))
#         answer_text = answer_text.strip()

#         #group source by files and remove duplicates
#         source_map = defaultdict(set)
#         for doc in docs:
#             page = doc.metadata.get('page')
#             file_name = doc.metadata.get('source')

#             if page in used_pages:
#                 source_map[file_name].add(page)

#         sources = []

#         for file_name, pages in source_map.items():
#             sources.append(
#                 {
#                     'file':file_name,
#                     'pages':sorted(pages)
#                 }
#             )

#         # for doc in docs:
#         #     # print(type(docs))
#         #     # print(doc)
#         #     sources.append(
#         #         {
#         #             'file':doc.metadata['source'],
#         #             'page':doc.metadata['page']
#         #         }
#         #     )

#         return Response(
#             {
#             'answer' : answer_text,
#             'sources' : sources
#             }
#         )

import re
from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Documents, ChatSession, ChatMessage
from .serializers import DocumentUploadSerializer
from .services.parser import extract_text
from .services.chunker import create
from .services.embeddings import vector_db
from .services.rag_pipeline import llm
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics
from langchain.retrievers.multi_query import MultiQueryRetriever
from collections import defaultdict


class UploadDocumentView(generics.CreateAPIView):
    queryset = Documents.objects.all()
    serializer_class = DocumentUploadSerializer


class ProcessDocumentView(APIView):
    def post(self, request, document_id):
        document = Documents.objects.get(
            id=document_id
        )
        print("DOCUMENT:", document.id)
        print("FILE:", document.file)

        pages = extract_text(
            document.file.path
        )
        all_chunks = []
        all_metadatas = []

        for page_data in pages:
            page_number = page_data['page']
            text = page_data['text']

            print("TEXT LENGTH:", len(text))
            print(text[:500])

            chunks = create(text)
            print('Chunks:', len(chunks))
            print(chunks[:2])

            if not chunks:
                # no chunks for this page, just skip it instead of
                # bailing out of the whole document
                continue

            for idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append(
                    {
                        'document_id': document.id,
                        'source': document.file.name,
                        'page': page_number,
                        'chunk_id': idx
                    }
                )

        if not all_chunks:
            return Response(
                {
                    'error': 'No text chunks created from documents'
                },
                status=400
            )

        vector_db.add_texts(
            texts=all_chunks,
            metadatas=all_metadatas
        )

        document.processed = True
        document.save()

        return Response(
            {
                'messages': 'document processed'
            }
        )


class CreateSessionView(APIView):
    def post(self, request):
        session = ChatSession.objects.create(
            title='New Chat'
        )

        return Response(
            {
                'session_id': session.id,
                'title': session.title
            }
        )


class ChatView(APIView):
    def post(self, request, session_id):
        question = request.data.get('question')

        if not question:
            return Response(
                {'error': 'question is required'},
                status=400
            )
        try:
            session = ChatSession.objects.get(
                id=session_id
            )
        except ChatSession.DoesNotExist:
            return Response(
                {'error': 'session not found'},
                status=404
            )

        # get previous chat history
        history_message = ChatMessage.objects.filter(
            session=session
        ).order_by('created_at')

        history = ""
        for msg in history_message:
            history += f"{msg.role} : {msg.context}\n"

        # Retrieve relevant docs
        retriever = vector_db.as_retriever(
            search_kwargs={'k': 8}
        )

        docs = retriever.invoke(question)

        # Build context with page numbers labeled so the LLM can
        # actually tell which page each chunk came from. Without this
        # the model has no way to know real page numbers and will guess.
        context = '\n\n'.join(
            f"[Page {doc.metadata.get('page')}]\n{doc.page_content}"
            for doc in docs
        )

        prompt = f"""
        You are a helpful RAG assistant.
        Answer only from the document context below.

        previous conversation:{history}

        document Context : {context}

        Question : {question}

        Rules:
        1. Use document context first.
        2. Use conversation history to resolve references like:
            - it
            - they
            - that event
            - this topic
        3. If the answer is not present in context, say:
        "I couldn't find that information."
        4. Do not mention page numbers inside the answer text itself.
        5. Only list a page in PAGES_USED if you actually used information
           from that page's content to construct the answer. Do not list
           every page that was provided in the context, only the ones
           whose content you relied on.
        6. At the very end of your response, on its own line, return
           exactly in this format (no extra spaces, no extra words):
        PAGES_USED:comma,separated,page,numbers

        Example:
        The answer goes here.
        PAGES_USED:3,7
        """

        answer = llm.invoke(prompt)

        # save user message
        ChatMessage.objects.create(
            session=session,
            role='user',
            context=question
        )

        # save assistant message
        ChatMessage.objects.create(
            session=session,
            role='assistant',
            context=answer.content
        )

        raw_answer = answer.content
        print('=' * 50)
        print(raw_answer)
        print('=' * 50)

        used_pages = []

        # Use a case-insensitive regex that tolerates spaces around the
        # colon (e.g. "PAGES_USED : 4" or "PAGES_USED:4") since LLM output
        # formatting is not perfectly consistent.
        match = re.search(
            r'PAGES_USED\s*:\s*(.*)',
            raw_answer,
            re.IGNORECASE
        )

        if match:
            answer_text = raw_answer[:match.start()].strip()
            pages_text = match.group(1)
        else:
            answer_text = raw_answer.strip()
            pages_text = ""

        # This loop now runs unconditionally (previously it was nested
        # inside the else-branch, so it never ran when PAGES_USED was
        # actually present).
        for p in pages_text.split(","):
            p = p.strip()
            if p.isdigit():
                used_pages.append(int(p))

        # group sources by file and remove duplicates, only keeping
        # pages the model actually says it used
        source_map = defaultdict(set)
        for doc in docs:
            page = doc.metadata.get('page')
            file_name = doc.metadata.get('source')

            if page in used_pages:
                source_map[file_name].add(page)

        sources = []
        for file_name, pages in source_map.items():
            sources.append(
                {
                    'file': file_name,
                    'pages': sorted(pages)
                }
            )

        return Response(
            {
                'answer': answer_text,
                'sources': sources
            }
        )