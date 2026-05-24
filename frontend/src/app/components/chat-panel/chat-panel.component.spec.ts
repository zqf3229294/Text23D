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

    expect(spy).toHaveBeenCalledOnceWith('make a cube');
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
    expect(links).toEqual(['STEP', 'GLB', 'Script', 'Log']);
  });
});
