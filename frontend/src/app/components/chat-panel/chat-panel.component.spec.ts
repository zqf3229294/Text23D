import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { ChatPanelComponent } from './chat-panel.component';
import { ApiService } from '../../services/api.service';

describe('ChatPanelComponent', () => {
  let fixture: ComponentFixture<ChatPanelComponent>;
  let component: ChatPanelComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatPanelComponent],
      providers: [
        {
          provide: ApiService,
          useValue: {
            artifactUrl: (id: string, kind: string) => `/artifacts/${id}/${kind}`,
            imageAttachmentUrl: (conversationId: string, attachmentId: string) =>
              `/images/${conversationId}/${attachmentId}`,
            generationEventAssetUrl: (generationId: string, eventId: string) =>
              `data:image/svg+xml,%3Csvg%20data-id='${generationId}-${eventId}'/%3E`,
            createConversation: () => of()
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ChatPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('emits trimmed prompt and clears the composer', () => {
    const spy = jasmine.createSpy('send');
    component.send.subscribe(spy);
    component.draft = '  make a cube  ';

    component.submit();

    expect(spy).toHaveBeenCalledOnceWith({ content: 'make a cube', images: [] });
    expect(component.draft).toBe('');
  });

  it('does not emit blank prompts', () => {
    const spy = jasmine.createSpy('send');
    component.send.subscribe(spy);
    component.draft = '   ';

    component.submit();

    expect(spy).not.toHaveBeenCalled();
  });

  it('renders artifact links for a completed generation', () => {
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'succeeded',
      prompt: 'make a cube',
      assistant_summary: 'done',
      error: null,
      attempt_count: 1,
      artifacts: {
        step: true,
        glb: true,
        stl: true,
        native: true,
        script: true,
        log: true
      },
      created_at: 'now',
      updated_at: 'now'
    };

    fixture.detectChanges();

    const links = Array.from(
      fixture.nativeElement.querySelectorAll('.artifact-links a') as NodeListOf<Element>
    ).map((link) => link.textContent?.trim());
    expect(links).toEqual(['STEP', 'GLB', 'STL', 'FreeCAD', 'Script', 'Log']);
  });

  it('renders frozen worked time for a completed generation', () => {
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'succeeded',
      prompt: 'make a cube',
      assistant_summary: 'done',
      error: null,
      attempt_count: 1,
      artifacts: {
        step: false,
        glb: false,
        stl: false,
        native: false,
        script: false,
        log: false
      },
      created_at: '2026-07-04T00:00:00.000Z',
      updated_at: '2026-07-04T00:02:05.000Z'
    };

    fixture.detectChanges();

    const workedTime = fixture.nativeElement.querySelector('.worked-time') as HTMLElement;
    expect(workedTime.textContent?.trim()).toBe('Worked for 2 m 05 s');
  });

  it('renders live worked time for an active generation', () => {
    component.currentTimeMs = Date.parse('2026-07-04T00:01:09.000Z');
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'running',
      prompt: 'make a cube',
      assistant_summary: null,
      error: null,
      attempt_count: 1,
      artifacts: {
        step: false,
        glb: false,
        stl: false,
        native: false,
        script: false,
        log: false
      },
      created_at: '2026-07-04T00:00:00.000Z',
      updated_at: '2026-07-04T00:00:04.000Z'
    };

    fixture.detectChanges();

    const workedTime = fixture.nativeElement.querySelector('.worked-time') as HTMLElement;
    expect(workedTime.textContent?.trim()).toBe('Worked for 1 m 09 s');
  });

  it('renders streamed screenshot events', () => {
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'running',
      prompt: 'make a flange',
      assistant_summary: null,
      error: null,
      attempt_count: 1,
      artifacts: {
        step: false,
        glb: false,
        stl: false,
        native: false,
        script: false,
        log: false
      },
      created_at: 'now',
      updated_at: 'now'
    };
    component.events = [
      {
        id: 'evt_1',
        generation_id: 'gen_1',
        event_type: 'screenshot',
        message: 'Captured FreeCAD view update.',
        tool_name: 'get_view',
        data: {},
        has_asset: true,
        created_at: new Date().toISOString()
      }
    ];

    fixture.detectChanges();

    const image = fixture.nativeElement.querySelector('.event img') as HTMLImageElement;
    expect(image.getAttribute('src')).toContain('gen_1-evt_1');
  });
});
